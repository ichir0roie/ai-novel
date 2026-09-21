#!/usr/bin/env python3
"""`worlds/` の md を db へ読み戻す。`export_db.py` の逆。

自己参照 FK(`parent_id` `parent_event_id` `parent_term_id` のような、自分の
テーブルを指す外部キー)を持つテーブルは、`export_db` と同じ規則で**階層を
再帰的にたどって**読み戻す。ディレクトリは、その中にある「自分自身」の md
(ディレクトリ名と同じ `tag`、`tag` が無ければ同じ `id` を持つファイル)を
まず読み、それ以外のファイル・サブディレクトリはその子として親の列
(`parent_id` など)に自分の id を書き込む。自己参照 FK を持たないテーブルは
これまで通り一段だけを読む。

置き場所(`worlds/{table_name}/...`)からテーブル名を読み、`tag`・階層上の
親は置き場所そのものから読む。ファイル名の `id` が db に無ければ(あるいは
`id` も `tag` も無ければ)、**新規レコードとして自動採番して作る。**
`id` があって既存なら上書きする。`text` は `# text` 見出し以降の本文を
そのまま使う。`Stamp` 型の列は `y/mm/dd HH:MM:SS` 形式の文字列として読み、
`Stamp.parse` で戻す。

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
from DEM.tool.markdown.export_db import self_ref_column

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


def _parse_stem(stem: str) -> tuple[int | None, str | None]:
    id_part, sep, tag_part = stem.partition("_")
    if not (sep and id_part.isdigit()):
        id_part, tag_part = "", stem
    row_id = int(id_part) if id_part else None
    return row_id, (tag_part or None)


def _upsert(
    session, model: type, columns: set[str], stamp_columns: set[str], path: str,
    parent_column: str | None, parent_value,
):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    filename = os.path.basename(path)
    row_id, tag = _parse_stem(filename[: -len(".md")])

    data, text = _parse(content, path)
    data.pop("id", None)
    data["tag"] = tag
    if parent_column:
        data.pop(parent_column, None)

    unknown = set(data) - columns
    if unknown:
        raise ImportDbError(f"{path}: スキーマに無い欄 {sorted(unknown)}")

    values = {}
    for key, value in data.items():
        if key in stamp_columns and value not in (None, ""):
            value = Stamp.parse(value)
        values[key] = value
    values["text"] = text
    if parent_column:
        values[parent_column] = parent_value

    row = session.get(model, row_id) if row_id is not None else None
    if row is None:
        row = model(**values)
        session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    session.flush()
    return row


def _self_file(dir_path: str, dirname: str) -> str | None:
    """`dir_path` の直下から、ディレクトリ自身を表す md(`dirname` と同じ
    `tag`、無ければ同じ `id` を持つファイル)を一つだけ探す。"""
    found = None
    for entry in sorted(os.listdir(dir_path)):
        full = os.path.join(dir_path, entry)
        if os.path.isdir(full) or not entry.endswith(".md"):
            continue
        row_id, tag = _parse_stem(entry[: -len(".md")])
        matches = tag == dirname or (tag is None and row_id is not None and str(row_id) == dirname)
        if matches:
            if found is not None:
                raise ImportDbError(f"{dir_path}: 自身を表す md が複数ある({found}, {full})")
            found = full
    return found


def _process_node_dir(
    session, model: type, columns: set[str], stamp_columns: set[str],
    dir_path: str, dirname: str, parent_column: str, parent_value, counter: list[int],
) -> None:
    self_path = _self_file(dir_path, dirname)
    if self_path is None:
        raise ImportDbError(
            f"{dir_path}: 自身を表す md が見当たらない"
            f"(ディレクトリ名 {dirname!r} と同じ tag か id のファイルが要る)")

    self_row = _upsert(session, model, columns, stamp_columns, self_path, parent_column, parent_value)
    counter[0] += 1

    for entry in sorted(os.listdir(dir_path)):
        full = os.path.join(dir_path, entry)
        if full == self_path:
            continue
        if os.path.isdir(full):
            _process_node_dir(session, model, columns, stamp_columns, full, entry, parent_column, self_row.id, counter)
        elif entry.endswith(".md"):
            _upsert(session, model, columns, stamp_columns, full, parent_column, self_row.id)
            counter[0] += 1


def _process_table_dir(
    session, model: type, columns: set[str], stamp_columns: set[str],
    table_dir: str, parent_column: str,
) -> int:
    counter = [0]
    for entry in sorted(os.listdir(table_dir)):
        full = os.path.join(table_dir, entry)
        if os.path.isdir(full):
            _process_node_dir(session, model, columns, stamp_columns, full, entry, parent_column, None, counter)
        elif entry.endswith(".md"):
            _upsert(session, model, columns, stamp_columns, full, parent_column, None)
            counter[0] += 1
    return counter[0]


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
            parent_column = self_ref_column(model)

            if parent_column:
                counts[table_name] = _process_table_dir(
                    session, model, columns, stamp_columns, table_dir, parent_column)
            else:
                count = 0
                for filename in sorted(os.listdir(table_dir)):
                    if not filename.endswith(".md"):
                        continue
                    _upsert(session, model, columns, stamp_columns,
                            os.path.join(table_dir, filename), None, None)
                    count += 1
                counts[table_name] = count

        session.commit()

    return counts


if __name__ == "__main__":
    import_db()
