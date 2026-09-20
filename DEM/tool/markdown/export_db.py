#!/usr/bin/env python3
"""db の `MarkdownBase` を継ぐ全テーブルを `worlds/` の下へ md として書き出す。

`schema.py` に列挙されたテーブルだけを対象にする(継承関係で自動的に拾う。
テーブルが増えても、ここを直す必要はない)。置き場所は

    worlds/{table_name}/{id or ""}_{tag or ""}.md

の一段だけで、親子関係などの入れ子はしない。**毎回 `worlds/` をまるごと
消してから書き直す。**

内容は

    # data
    ```json
    {列名: 値, ...}
    ```

    # text
    {text}

`text` 列だけ本文側に出し、それ以外の列(`id` `tag` を含む)は `data` の
json に入れる。`Stamp` 型の値は `y/mm/dd HH:MM:SS` の文字列にして出す。
"""
from __future__ import annotations

import json
import os
import shutil
from decimal import Decimal

from DEM.db.schema import Base, MarkdownBase, get_session
from DEM.db.stamp import Stamp

WORLDS_ROOT = "worlds"

__all__ = ["WORLDS_ROOT", "ExportError", "export_db"]


class ExportError(ValueError):
    """書き出せないレコードがあった。"""


def _markdown_models() -> list[type]:
    return [
        mapper.class_ for mapper in Base.registry.mappers
        if issubclass(mapper.class_, MarkdownBase) and mapper.class_ is not MarkdownBase
    ]


def _serialize(value):
    if isinstance(value, Stamp):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def _render(data: dict, text: str) -> str:
    data_json = json.dumps(data, ensure_ascii=False, indent=2)
    return f"# data\n```json\n{data_json}\n```\n\n# text\n{text}\n"


ignore_columns = [
    "text", "tag", "id"
]


def export_db(root: str = WORLDS_ROOT) -> dict[str, int]:
    """db を md へ書き出して、テーブル名ごとの件数を辞書で返す。"""
    if os.path.exists(root):
        shutil.rmtree(root)

    counts: dict[str, int] = {}
    with get_session() as session:
        for model in _markdown_models():
            table_name = model.__tablename__
            rows = session.query(model).order_by(model.id.asc()).all()

            table_dir = os.path.join(root, table_name)
            os.makedirs(table_dir, exist_ok=True)

            for row in rows:
                data = {
                    column.key: _serialize(getattr(row, column.key))
                    for column in model.__table__.columns
                    if column.key not in ignore_columns
                }
                text = row.text or ""
                filename = f"{data.get('id') or ''}_{data.get('tag') or ''}.md"
                path = os.path.join(table_dir, filename)
                if os.path.exists(path):
                    raise ExportError(f"ファイル名が重複した: {path}")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(_render(data, text))

            counts[table_name] = len(rows)

    return counts


if __name__ == "__main__":
    export_db()
