#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
from decimal import Decimal

from db.schema import WORLDS_ROOT, Base, MarkdownBase, get_novel_session
from db.stamp import Stamp
from tool.map.render import render_maps
from tool.markdown import sync_stamp
from tool.relation.render import render_relations


__all__ = ["WORLDS_ROOT", "ExportError", "export_db"]

IGNORE_COLUMNS = {"directory_path", "filename"}


class ExportError(ValueError):
    pass


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


def _render(data: dict, sections: dict[str, str]) -> str:
    data_json = json.dumps(data, ensure_ascii=False, indent=2)
    body = "".join(f"\n# {name}\n{value}\n" for name, value in sections.items())
    return f"# data\n```json\n{data_json}\n```\n{body}"


def _row_data(model: type, row, ignore_columns: set[str]) -> dict:
    ignored = ignore_columns | set(model.TEXT_SECTIONS)
    return {
        column.key: _serialize(getattr(row, column.key))
        for column in model.__table__.columns
        if column.key not in ignored
    }


def _sections(model: type, row) -> dict[str, str]:
    return {name: getattr(row, name) or "" for name in model.TEXT_SECTIONS}


def _write(path: str, data: dict, sections: dict[str, str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(_render(data, sections))


def export_db(root: str = WORLDS_ROOT) -> dict[str, int]:
    if os.path.exists(root):
        shutil.rmtree(root)

    counts: dict[str, int] = {}
    with get_novel_session() as session:
        for model in _markdown_models():
            table_name = model.__tablename__
            rows = session.query(model).order_by(model.id.asc()).all()

            table_dir = os.path.join(root, table_name)
            os.makedirs(table_dir, exist_ok=True)

            written: set[str] = set()
            for row in rows:
                dir_path = os.path.join(table_dir, row.directory_path) if row.directory_path else table_dir
                path = os.path.join(dir_path, row.markdown_name)
                if path in written:
                    # 名前に id を含まないテーブルで同名になったら、id を頭に付けた(import が読める)名前へ逃がす
                    path = os.path.join(dir_path, f"{row.id}_{row.markdown_name}")
                written.add(path)
                _write(path, _row_data(model, row, IGNORE_COLUMNS), _sections(model, row))

            counts[table_name] = len(rows)

        render_maps(session, root)
        render_relations(session, root)

    sync_stamp.mark_synced(root)
    return counts


if __name__ == "__main__":
    export_db()
