#!/usr/bin/env python3
"""`worlds/` の md を db へ読み戻す。`export_db.py` の逆。

置き場所(`worlds/{table_name}/{id or ""}_{tag or ""}.md`)からテーブル名・
`id`・`tag` を読み、`# data` の json からそれ以外の列の値を復元する。
`id` が入っていればそのレコードを更新し(無ければ `ImportDbError`)、
無ければ新規に作る。`text` は `# text` 見出し以降の本文をそのまま使う。
`Stamp` 型の列は `y/mm/dd HH:MM:SS` 形式の文字列として読み、`Stamp.parse`
で戻す。

作者が手で置いた素の md(`export_db` 形式に従っていないもの)も新規レコード
として取り込む。ファイル名に `_` が無ければ、`id` 無しでファイル名の
拡張子抜きの部分をそのまま `tag` にする。本文に `# data` ブロックが無ければ
列はすべて空のまま、ファイル全体をそのまま `text` として扱う。
"""
from __future__ import annotations

from datetime import datetime
import json
import os
import re
import shutil

from DEM.db.schema import Base, MarkdownBase, StampType, get_session
from DEM.db.stamp import Stamp

WORLDS_ROOT = "worlds"

__all__ = ["WORLDS_ROOT", "ImportDbError", "import_db"]


class ImportDbError(ValueError):
    """md を読み戻せなかった。"""


_DATA_RE = re.compile(r"#\s*data\s*```json\s*(.*?)\s*```", re.S)
_TEXT_RE = re.compile(r"#\s*text\s*\n(.*)\Z", re.S)


def _markdown_models() -> dict[str, type]:
    return {
        mapper.class_.__tablename__: mapper.class_
        for mapper in Base.registry.mappers
        if issubclass(mapper.class_, MarkdownBase) and mapper.class_ is not MarkdownBase
    }


def _parse(content: str, path: str) -> tuple[dict, str]:
    data_match = _DATA_RE.search(content)
    if not data_match:
        return {}, content.rstrip("\n")
    data = json.loads(data_match.group(1))
    text_match = _TEXT_RE.search(content)
    text = text_match.group(1).rstrip("\n") if text_match else ""
    return data, text


def import_db(root: str = WORLDS_ROOT) -> dict[str, int]:
    """md を db へ読み戻して、テーブル名ごとの件数を辞書で返す。"""
    date_str = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = f"backup/{date_str}.db.bk"
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    shutil.copy("novel.db", backup_path)

    models_by_table = _markdown_models()

    counts: dict[str, int] = {}
    with get_session() as session:
        for table_name, model in models_by_table.items():
            table_dir = os.path.join(root, table_name)
            if not os.path.isdir(table_dir):
                continue

            columns = {column.key for column in model.__table__.columns}
            stamp_columns = {
                column.key for column in model.__table__.columns
                if isinstance(column.type, StampType)
            }

            count = 0
            for filename in sorted(os.listdir(table_dir)):
                if not filename.endswith(".md"):
                    continue
                path = os.path.join(table_dir, filename)
                with open(path, encoding="utf-8") as f:
                    content = f.read()

                stem = filename[: -len(".md")]
                id_part, sep, tag_part = stem.partition("_")
                if not (sep and id_part.isdigit()):
                    id_part, tag_part = "", stem
                row_id = int(id_part) if id_part else None

                data, text = _parse(content, path)
                data.pop("id", None)
                data["tag"] = tag_part or None

                unknown = set(data) - columns
                if unknown:
                    raise ImportDbError(f"{path}: スキーマに無い欄 {sorted(unknown)}")

                values = {}
                for key, value in data.items():
                    if key in stamp_columns and value not in (None, ""):
                        value = Stamp.parse(value)
                    values[key] = value
                values["text"] = text

                if row_id is not None:
                    row = session.get(model, row_id)
                    if row is None:
                        continue
                    for key, value in values.items():
                        setattr(row, key, value)
                else:
                    row = model(**values)
                    session.add(row)

                count += 1

            counts[table_name] = count

        session.commit()

    return counts


if __name__ == "__main__":
    import_db()
