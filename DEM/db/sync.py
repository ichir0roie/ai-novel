from glob import glob
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
            for record in records:
                with open(record.filepath, "r", encoding="utf-8") as f:
                    text = f.read()
                record.text = text
        s.commit()


__file_type_map: dict[str, type[MarkdownBase]] = {cls.__tablename__: cls for cls in markdown_base_tables()}


def import_db():
    files = glob("worlds/**/*.md", recursive=True)
    for file in files:
        file_type = file.split("/")[2]


def dump_record_to_markdown(record: MarkdownBase) -> str:
    path = record.filepath
    text = record.text

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def export_db():
    markdown_tables = markdown_base_tables()
    with get_session() as s:
        for markdown_table in markdown_tables:
            records = s.scalars(select(markdown_table)).all()
            for record in records:
                dump_record_to_markdown(record)
