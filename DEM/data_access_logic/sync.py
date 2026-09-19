import os
from glob import glob
import shutil

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from DEM.db.schema import *


# def markdown_base_tables() -> list[type[MarkdownBase]]:
#     """`MarkdownBase` を継承する全クラスを列挙する。

#     md ↔ db を往復させるテーブルはここに集まる。テーブルを増やしたときに
#     import/export 側を手で足さずに済むよう、継承関係から拾う。
#     """
#     seen = []
#     stack = MarkdownBase.__subclasses__()
#     while stack:
#         cls = stack.pop()
#         if cls not in seen:
#             seen.append(cls)
#             stack.extend(cls.__subclasses__())
#     return seen


# def update_db():
#     markdown_tables = markdown_base_tables()
#     with get_session() as s:
#         for markdown_table in markdown_tables:
#             records = s.scalars(select(markdown_table)).all()
#             # for record in records:
#         #         with open(record, "r", encoding="utf-8") as f:
#         #             text = f.read()
#         #         record.text = text
#         # s.commit()


# __file_type_map: dict[str, type[MarkdownBase]] = {cls.__tablename__: cls for cls in markdown_base_tables()}


# def import_db():
#     files = glob("worlds/**/*.md", recursive=True)
#     for file in files:
#         file_type = file.split("/")[2]


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


def _cross_owner(record: MarkdownBase) -> tuple[type[MarkdownBase], int, str] | None:
    """自己参照ではなく、別のテーブルのレコードの配下に置かれるべきものを返す。

    `(持ち主のクラス, 持ち主の id, 持ち主のフォルダ内でのサブフォルダ名)` を返す。
    サブフォルダ名は基本そのテーブル名だが、`Episode` の `episodes` のように
    見出し語が違うものだけ個別に指定する。

    - `Event` は `character_id` → `object_id` の順で持ち主を探す（人物の行動なら
      人物の配下、個体の行動なら個体の配下）
    - `CharacterEmotion`（drive）は `character_id` の配下
    - `Episode` は `story_id` の配下、`episodes` フォルダに
    - どれでもなければ `None`（そのテーブル自身の直下に置く）
    """
    if isinstance(record, Event):
        if record.character_id is not None:
            return (Character, record.character_id, "events")
        if record.object_id is not None:
            return (Object, record.object_id, "events")
        return None
    if isinstance(record, CharacterEmotion):
        if record.character_id is not None:
            return (Character, record.character_id, CharacterEmotion.__tablename__)
        return None
    if isinstance(record, Episode):
        return (Story, record.story_id, "episodes")
    return None


def dump_record_to_markdown(record: MarkdownBase, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(record.text)


migration_root_markdown_tables: tuple[type[MarkdownBase]] = (
    Location,
    Term,
    Kind,
    Object,
    Skill,
    Character,
    Story,
)

child_relation_map: dict[type[MarkdownBase], tuple[type[MarkdownBase]]] = {
    Character: (
        CharacterEmotion,
        Event,
    ),
    Object: (
        Event,
    ),
    Story: (
        Episode,
    )
}


class MarkdownExporter:

    def load_query(self, parent_id: int | None):
        raise NotImplementedError

    def export_record(self, record):
        raise NotImplementedError

    def export(self, s: Session):
        records = s.scalars(self.load_query()).all()
        for record in records:
            self.export_record(record)

# TODO 各テーブルのエクスポーター


def export_db():

    shutil.rmtree("worlds", ignore_errors=True)

    with get_session() as s:
        export_classes: tuple[type[MarkdownExporter]] = ()
        for export_class in export_classes:
            exporter = export_class()
            records = s.scalars(exporter.load_query()).all()
            for record in records:
                exporter.export()
