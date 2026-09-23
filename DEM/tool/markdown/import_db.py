#!/usr/bin/env python3
"""`worlds/` の md を db へ読み戻す。`export_db.py` の逆。

"""
from __future__ import annotations

from datetime import datetime
import json
import os
import re
import shutil

from DEM.db.schema import NOVEL_DB_PATH, Base, MarkdownBase, StampType, get_novel_session
from DEM.db.stamp import Stamp
from DEM.tool.markdown import export_db

WORLDS_ROOT = "worlds"

__all__ = ["WORLDS_ROOT", "ImportDbError", "import_db"]


class ImportDbError(ValueError):
    """md を読み戻せなかった。"""


_DATA_RE = re.compile(r"#\s*data\s*```json\s*(.*?)\s*```", re.S)


def _section_re(names: tuple[str, ...]) -> re.Pattern:
    return re.compile(r"^#[ \t]*(" + "|".join(re.escape(n) for n in names) + r")[ \t]*$", re.M)


def _markdown_models() -> dict[str, type]:
    return {
        mapper.class_.__tablename__: mapper.class_
        for mapper in Base.registry.mappers
        if issubclass(mapper.class_, MarkdownBase) and mapper.class_ is not MarkdownBase
    }


def _parse(content: str, names: tuple[str, ...]) -> tuple[dict, dict[str, str]]:
    sections = {name: "" for name in names}
    data_match = _DATA_RE.search(content)
    if not data_match:
        sections["text"] = content.rstrip("\n")
        return {}, sections
    data = json.loads(data_match.group(1))

    rest = content[data_match.end():]
    # 同じ見出しが本文中に再び出ても節の切れ目にしない(最初の一つだけを見出しとして扱う)
    heads = []
    for match in _section_re(names).finditer(rest):
        if match.group(1) not in {name for name, _ in heads}:
            heads.append((match.group(1), match))
    for index, (name, match) in enumerate(heads):
        stop = heads[index + 1][1].start() if index + 1 < len(heads) else len(rest)
        sections[name] = rest[match.end():stop].strip("\n")
    return data, sections


def _upsert(
    session, model: type, columns: set[str], stamp_columns: set[str],
    path: str, directory_path: str | None,
):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    stem = os.path.basename(path)[: -len(".md")]
    row_id, stem_values = model.parse_markdown_stem(stem)

    data, sections = _parse(content, model.TEXT_SECTIONS)
    data_id = data.pop("id", None)
    if row_id is None and data_id is not None:
        row_id = int(data_id)
    data["directory_path"] = directory_path
    # `# data` にある欄はそれが勝つ。名前は `# data` に無い欄(filename や、手書き md の start/end)だけ埋める
    data.update({k: v for k, v in stem_values.items() if k not in data})

    unknown = set(data) - columns
    if unknown:
        raise ImportDbError(f"{path}: スキーマに無い欄 {sorted(unknown)}")

    values = {}
    for key, value in data.items():
        if key in stamp_columns and value not in (None, ""):
            value = Stamp.parse(value)
        values[key] = value
    values.update(sections)

    row = session.get(model, row_id) if row_id is not None else None
    if row is None:
        row = model(**values)
        session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    # 名前から自動で付く部分(人物名など)は filename に残さない。名前が変わったら md 名も追従する
    if row.filename is not None and row.filename == row.default_filename():
        row.filename = None
    session.flush()
    if row_id is None:
        # 採番した id を md 側にも残す(名前か `# data` のどちらかに入る)
        os.remove(path)
        export_db._write(os.path.join(os.path.dirname(path), row.markdown_name),
                         export_db._row_data(model, row, export_db.IGNORE_COLUMNS), sections)
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
    shutil.copy(NOVEL_DB_PATH, backup_path)

    models_by_table = _markdown_models()

    counts: dict[str, int] = {}
    with get_novel_session() as session:
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
