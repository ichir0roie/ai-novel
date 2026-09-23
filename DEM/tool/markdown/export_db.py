#!/usr/bin/env python3
"""db の `MarkdownBase` を継ぐ全テーブルを `worlds/` の下へ md として書き出す。
"""
from __future__ import annotations

import json
import os
import shutil
from decimal import Decimal

from DEM.db.schema import Base, MarkdownBase, get_novel_session
from DEM.db.stamp import Stamp
from DEM.tool.map.render import render_maps
from DEM.tool.relation.render import render_relations

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


def _filename(row) -> str:
    if not row.filename:
        return f"{row.id}.md"
    return f"{row.id}_{row.filename.replace('/', '／')}.md"


def _write(path: str, data: dict, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(_render(data, text))


def export_db(root: str = WORLDS_ROOT) -> dict[str, int]:
    """db を md へ書き出して、テーブル名ごとの件数を辞書で返す。"""
    # if os.path.exists(root):
    #     shutil.rmtree(root)

    counts: dict[str, int] = {}
    with get_novel_session() as session:
        for model in _markdown_models():
            table_name = model.__tablename__
            rows = session.query(model).order_by(model.id.asc()).all()

            table_dir = os.path.join(root, table_name)
            os.makedirs(table_dir, exist_ok=True)

            ignore_columns = {"text", "directory_path", "filename", "id"}

            for row in rows:
                dir_path = os.path.join(table_dir, row.directory_path) if row.directory_path else table_dir
                data = _row_data(model, row, ignore_columns)
                text = row.text or ""
                _write(os.path.join(dir_path, _filename(row)), data, text)

            counts[table_name] = len(rows)

        render_maps(session, root)
        render_relations(session, root)

    return counts


if __name__ == "__main__":
    export_db()
