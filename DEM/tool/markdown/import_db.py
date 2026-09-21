#!/usr/bin/env python3
"""`worlds/` の md を db へ読み戻す。`export_db.py` の逆。

`worlds/{table_name}/` の下を再帰的に歩いて `.md` を全て拾う。
`table_name` からテーブルが決まり、`table_name/` からの相対ディレクトリパスが
そのまま `directory_path` 列に入る(直下に置かれていれば空)。ファイル名は
`{id}.md` か `{id}_{filename}.md`。最初の `_` の手前(無ければ拡張子抜き
全体)が数字なら db 上の `id` として読み、その行を上書きする。数字でなければ
(あるいは `id` が db に無ければ)**新規レコードとして自動採番して作る。**
id を数字として読めたときだけ、`_` の後ろをそのまま `filename` 列に入れる
(無ければ空)。`text` は `# text` 見出し以降の本文をそのまま使う。`Stamp`
型の列は `y/mm/dd HH:MM:SS` 形式の文字列として読み、`Stamp.parse` で戻す。

作者が手で置いた素の md(`export_db` 形式に従っていないもの)も新規レコード
として取り込む。本文に `# data` ブロックが無ければ列はすべて空のまま、
ファイル全体をそのまま `text` として扱う。置き場所(ディレクトリ)だけは
`directory_path` として読む。
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


def _upsert(
    session, model: type, columns: set[str], stamp_columns: set[str],
    path: str, directory_path: str | None,
):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    stem = os.path.basename(path)[: -len(".md")]
    id_part, _, filename_part = stem.partition("_")
    row_id = int(id_part) if id_part.isdigit() else None

    data, text = _parse(content, path)
    data.pop("id", None)
    data["directory_path"] = directory_path
    data["filename"] = filename_part if row_id is not None and filename_part else None

    unknown = set(data) - columns
    if unknown:
        raise ImportDbError(f"{path}: スキーマに無い欄 {sorted(unknown)}")

    values = {}
    for key, value in data.items():
        if key in stamp_columns and value not in (None, ""):
            value = Stamp.parse(value)
        values[key] = value
    values["text"] = text

    row = session.get(model, row_id) if row_id is not None else None
    if row is None:
        row = model(**values)
        session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    session.flush()
    return row


def _process_table_dir(
    session, model: type, columns: set[str], stamp_columns: set[str], table_dir: str,
) -> int:
    count = 0
    for dirpath, _dirnames, filenames in os.walk(table_dir):
        relative = os.path.relpath(dirpath, table_dir)
        directory_path = None if relative == "." else relative.replace(os.sep, "/")
        for filename in sorted(filenames):
            if not filename.endswith(".md"):
                continue
            _upsert(session, model, columns, stamp_columns, os.path.join(dirpath, filename), directory_path)
            count += 1
    return count


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

            counts[table_name] = _process_table_dir(session, model, columns, stamp_columns, table_dir)

        session.commit()

    return counts


if __name__ == "__main__":
    import_db()
