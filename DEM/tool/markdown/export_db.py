#!/usr/bin/env python3
"""db の `MarkdownBase` を継ぐ全テーブルを `worlds/` の下へ md として書き出す。

`schema.py` に列挙されたテーブルだけを対象にする(継承関係で自動的に拾う。
テーブルが増えても、ここを直す必要はない)。

**自分のテーブルを指す外部キー列(`parent_id` `parent_event_id`
`parent_term_id` のような自己参照 FK)を持つテーブルは、階層化して書き出す。**
親から子へ、木の上から順に再帰的にたどり、`tag` をディレクトリ名にして
入れ子にする(`tag` が無い行は `id` を数字のままディレクトリ名に使う)。
子を持つ行は、自分のディレクトリの**中に**自分自身の md を置く
(`term/魔力/13_魔力.md` が「魔力」自身、`term/魔力/魔力灯り/14_魔力灯り.md`
がその子)。子を持たない行はそのまま親のディレクトリ直下に置く。
自己参照 FK を持たないテーブルは、これまで通り

    worlds/{table_name}/{id or ""}_{tag or ""}.md

の一段だけで並べる。**毎回 `worlds/` をまるごと消してから書き直す。**

内容は

    # data
    ```json
    {列名: 値, ...}
    ```

    # text
    {text}

`text` 列だけ本文側に出し、それ以外の列は `data` の json に入れる。ただし
`id` `tag`、および階層化テーブルの自己参照 FK 列は、ファイル名・置き場所
そのものが情報を持つので `data` には出さない。`Stamp` 型の値は
`y/mm/dd HH:MM:SS` の文字列にして出す。
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


def self_ref_column(model: type) -> str | None:
    """`model` が自分のテーブルを指す外部キー列を持っていれば、その列名を返す。

    `Location.parent_id` `Event.parent_event_id` `Term.parent_term_id` の
    ように、schema.py に列挙された自己参照 FK を汎用に検出する
    (テーブルごとに列名をハードコードしない)。
    """
    for column in model.__table__.columns:
        for fk in column.foreign_keys:
            if fk.column.table is model.__table__:
                return column.key
    return None


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
    with open(path, "w", encoding="utf-8") as f:
        f.write(_render(data, text))


def _dir_name(row) -> str:
    return row.tag if row.tag else str(row.id)


def _write_tree(
    dir_path: str, nodes: list, children_by_parent: dict, model: type, ignore_columns: set[str],
) -> None:
    for row in nodes:
        filename = f"{row.id or ''}_{row.tag or ''}.md"
        data = _row_data(model, row, ignore_columns)
        text = row.text or ""

        kids = children_by_parent.get(row.id, [])
        if kids:
            node_dir = os.path.join(dir_path, _dir_name(row))
            os.makedirs(node_dir, exist_ok=True)
            _write(os.path.join(node_dir, filename), data, text)
            _write_tree(node_dir, kids, children_by_parent, model, ignore_columns)
        else:
            _write(os.path.join(dir_path, filename), data, text)


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

            parent_column = self_ref_column(model)
            ignore_columns = {"text", "tag", "id"}
            if parent_column:
                ignore_columns.add(parent_column)

            if parent_column:
                children_by_parent: dict[int | None, list] = {}
                for row in rows:
                    children_by_parent.setdefault(getattr(row, parent_column), []).append(row)
                _write_tree(table_dir, children_by_parent.get(None, []), children_by_parent, model, ignore_columns)
            else:
                for row in rows:
                    filename = f"{row.id or ''}_{row.tag or ''}.md"
                    data = _row_data(model, row, ignore_columns)
                    text = row.text or ""
                    _write(os.path.join(table_dir, filename), data, text)

            counts[table_name] = len(rows)

    return counts


if __name__ == "__main__":
    export_db()
