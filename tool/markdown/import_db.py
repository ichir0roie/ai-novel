#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
import json
import os
import re
import shutil

from db.child_lists import ChildListError, load_children
from db.schema import NOVEL_DB_PATH, WORLDS_ROOT, Base, MarkdownBase, StampType, get_novel_session
from db.stamp import Stamp
from tool.markdown import export_db
from tool.markdown.sync_manifest import Manifest, digest, locked, read_text


__all__ = ["WORLDS_ROOT", "ImportDbError", "import_db", "import_changes"]


class ImportDbError(ValueError):
    pass


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
    path: str, directory_path: str | None, content: str, manifest: Manifest,
) -> tuple[object, bool]:
    """md を一件 db へ入れる。db 側も前回の同期から変わっていたら、衝突として True を返す。"""
    stem = os.path.basename(path)[: -len(".md")]
    row_id, stem_values = model.parse_markdown_stem(stem)

    data, sections = _parse(content, model.TEXT_SECTIONS)
    data_id = data.pop("id", None)
    if row_id is None and data_id is not None:
        row_id = int(data_id)
    data["directory_path"] = directory_path
    children = {name: data.pop(name) for name in model.CHILD_LISTS if name in data}
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
    entry = manifest.get(path)
    conflict = False
    if entry is not None and entry["table"] == model.__tablename__ and entry["id"] == row_id:
        conflict = row is None or digest(export_db.render_row(model, row)) != entry["db"]
    # md 名は前回の書き出し時の名前のままなので、`# data` で名前を直した md は直す前の名前と比べる
    default_filenames = {row.default_filename()} if row is not None else set()
    if row is None:
        row = model(**values)
        session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    for name, items in children.items():
        try:
            load_children(row, name, items)
        except ChildListError as error:
            raise ImportDbError(f"{path}: {error}") from error
    default_filenames.add(row.default_filename())
    # 名前から自動で付く部分(人物名など)は filename に残さない。名前が変わったら md 名も追従する
    if row.filename is not None and row.filename in default_filenames:
        row.filename = None
    session.flush()
    rendered = export_db.render_row(model, row)
    if row_id is None:
        # 採番した id を md 側にも残す(名前か `# data` のどちらかに入る)
        os.remove(path)
        path = os.path.join(os.path.dirname(path), row.markdown_name)
        export_db._write(path, rendered)
        content = rendered
    manifest.set(path, model.__tablename__, row.id, digest(content), digest(rendered))
    return row, conflict


def _unchanged_row(session, model: type, path: str, directory_path: str | None, content: str):
    """md が db の行をそのまま書き出した中身と同じなら、その行を返す(取り込まなくてよい)。"""
    stem = os.path.basename(path)[: -len(".md")]
    row_id, _stem_values = model.parse_markdown_stem(stem)
    if row_id is None:
        data_match = _DATA_RE.search(content)
        if not data_match:
            return None
        data_id = json.loads(data_match.group(1)).get("id")
        row_id = int(data_id) if data_id is not None else None
    row = session.get(model, row_id) if row_id is not None else None
    if (row is None or row.directory_path != directory_path
            or os.path.basename(path) != row.markdown_name
            or export_db.render_row(model, row) != content):
        return None
    return row


def _edited_files(root: str, manifest: Manifest) -> list[tuple[type, str, str | None, str]]:
    edited = []
    for table_name, model in _markdown_models().items():
        table_dir = os.path.join(root, table_name)
        for dirpath, _dirnames, filenames in os.walk(table_dir):
            relative = os.path.relpath(dirpath, table_dir)
            directory_path = None if relative == "." else relative.replace(os.sep, "/")
            for filename in sorted(filenames):
                if not filename.endswith(".md"):
                    continue
                path = os.path.join(dirpath, filename)
                content = read_text(path)
                if manifest.edited(path, content):
                    edited.append((model, path, directory_path, content))
    return edited


def _backup() -> None:
    date_str = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = f"backup/{date_str}.db.bk"
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    shutil.copy(NOVEL_DB_PATH, backup_path)


def import_changes(session, root: str, manifest: Manifest) -> dict:
    """前回の同期より後に手で直された(または足された)md だけを db へ入れる。commit はしない。

    db 側も同じ行を直していたら md の方を勝たせ、その md を `conflicts` に返す。
    """
    edited = []
    for model, path, directory_path, content in _edited_files(root, manifest):
        # 台帳が無い・古いだけで、db と同じ中身の md(git で両方そろって入ってきたものなど)は台帳に載せるだけにする
        row = _unchanged_row(session, model, path, directory_path, content)
        if row is None:
            edited.append((model, path, directory_path, content))
        else:
            manifest.set(path, model.__tablename__, row.id, digest(content), digest(content))
    if edited:
        _backup()
    counts: dict[str, int] = {}
    conflicts = []
    for model, path, directory_path, content in edited:
        columns = {column.key for column in model.__table__.columns}
        stamp_columns = {
            column.key for column in model.__table__.columns
            if isinstance(column.type, StampType)
        }
        _row, conflict = _upsert(session, model, columns, stamp_columns, path, directory_path, content, manifest)
        if conflict:
            conflicts.append(path)
        counts[model.__tablename__] = counts.get(model.__tablename__, 0) + 1
    return {"counts": counts, "conflicts": conflicts}


def import_db(root: str = WORLDS_ROOT) -> dict[str, int]:
    with locked(root):
        manifest = Manifest(root)
        with get_novel_session() as session:
            result = import_changes(session, root, manifest)
            session.commit()
        manifest.save()
    return result["counts"]
