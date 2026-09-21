#!/usr/bin/env python3
"""db の `MarkdownBase` を継ぐ全テーブルを `worlds/` の下へ md として書き出す。

`schema.py` に列挙されたテーブルだけを対象にする(継承関係で自動的に拾う。
テーブルが増えても、ここを直す必要はない)。

置き場所は

    worlds/{table_name}/{directory_path}/{id}.md

`directory_path` は各行が持つ列で、`worlds/{table_name}/` からの相対
ディレクトリパス。空ならテーブル直下にそのまま置く。**ディレクトリ構成は
`directory_path` の値だけで決まる。** `parent_id` `parent_event_id`
`parent_term_id` のような自己参照 FK は他の列と同じデータとして
`data` の json に出すだけで、置き場所には使わない
(`{name}/{name}.md` のように自分自身を表す特別なファイルを
ディレクトリ内に置く、という特殊パターンは無い)。

**毎回 `worlds/` をまるごと消してから書き直す。**

内容は

    # data
    ```json
    {列名: 値, ...}
    ```

    # text
    {text}

`text` 列だけ本文側に出し、それ以外の列は `data` の json に入れる。ただし
`id` `directory_path` は、ファイル名・置き場所そのものが情報を持つので
`data` には出さない。`Stamp` 型の値は `y/mm/dd HH:MM:SS` の文字列にして出す。
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


def _row_data(model: type, row, ignore_columns: set[str]) -> dict:
    return {
        column.key: _serialize(getattr(row, column.key))
        for column in model.__table__.columns
        if column.key not in ignore_columns
    }


def _write(path: str, data: dict, text: str) -> None:
    if os.path.exists(path):
        raise ExportError(f"ファイル名が重複した: {path}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(_render(data, text))


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

            ignore_columns = {"text", "directory_path", "id"}

            for row in rows:
                dir_path = os.path.join(table_dir, row.directory_path) if row.directory_path else table_dir
                data = _row_data(model, row, ignore_columns)
                text = row.text or ""
                _write(os.path.join(dir_path, f"{row.id}.md"), data, text)

            counts[table_name] = len(rows)

    return counts


if __name__ == "__main__":
    export_db()
