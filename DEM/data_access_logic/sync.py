import os
from glob import glob

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from DEM.db.schema import *


def markdown_base_tables() -> list[type[MarkdownBase]]:
    """`MarkdownBase` を継承する全クラスを列挙する。

    md ↔ db を往復させるテーブルはここに集まる。テーブルを増やしたときに
    import/export 側を手で足さずに済むよう、継承関係から拾う。
    """
    seen = []
    stack = MarkdownBase.__subclasses__()
    while stack:
        cls = stack.pop()
        if cls not in seen:
            seen.append(cls)
            stack.extend(cls.__subclasses__())
    return seen


def update_db():
    markdown_tables = markdown_base_tables()
    with get_session() as s:
        for markdown_table in markdown_tables:
            records = s.scalars(select(markdown_table)).all()
            # for record in records:
        #         with open(record, "r", encoding="utf-8") as f:
        #             text = f.read()
        #         record.text = text
        # s.commit()


__file_type_map: dict[str, type[MarkdownBase]] = {cls.__tablename__: cls for cls in markdown_base_tables()}


def import_db():
    files = glob("worlds/**/*.md", recursive=True)
    for file in files:
        file_type = file.split("/")[2]


def _self_parent_column(cls: type[MarkdownBase]) -> str | None:
    """同じ表を指す外部キー欄（`parent_id` `parent_term_id` など）があれば、
    その欄名を返す。無ければ `None`（そのテーブルは階層を持たない）。
    """
    mapper = sa_inspect(cls)
    for column in mapper.columns:
        if column.key == "id":
            continue
        for fk in column.foreign_keys:
            if fk.column.table is mapper.local_table:
                return column.key
    return None


def _record_name(record: MarkdownBase) -> str:
    """ファイル名・ディレクトリ名に使う、レコードの呼び名。"""
    name = getattr(record, "name", None) or getattr(record, "title", None)
    return str(name) if name else f"id{record.id}"


def relation_path(session: Session, record: MarkdownBase) -> str:
    """`relation`（自己参照の親欄）をたどって置き場所を組む。

    `worlds/{table_name}/<親.../>{name}.md` の形になる。親欄を持たない
    テーブルは `worlds/{table_name}/{name}.md` に置く。
    """
    cls = type(record)
    parent_column = _self_parent_column(cls)

    ancestors: list[str] = []
    current = record
    while parent_column is not None:
        parent_id = getattr(current, parent_column)
        if parent_id is None:
            break
        current = session.get(cls, parent_id)
        if current is None:
            break
        ancestors.append(_record_name(current))

    ancestors.reverse()
    segments = [cls.__tablename__, *ancestors, f"{_record_name(record)}.md"]
    return os.path.join("worlds", *segments)


def dump_record_to_markdown(record: MarkdownBase, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(record.text)


def export_db():
    """`MarkdownBase` を継承する全テーブルを md へ書き出す。

    置き場所は `relation_path` が決める。`Event` は他のどのテーブルの
    レコードからも参照されうる（`place_id` `character_id` `object_id`）ため、
    それらを書き終えたあとで最後に export する。
    """
    markdown_tables = markdown_base_tables()
    markdown_tables.sort(key=lambda cls: cls is Event)

    with get_session() as s:
        for markdown_table in markdown_tables:
            records = s.scalars(select(markdown_table)).all()
            for record in records:
                path = relation_path(s, record)
                dump_record_to_markdown(record, path)
