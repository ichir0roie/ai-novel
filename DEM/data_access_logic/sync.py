import os
from glob import glob
import shutil

from sqlalchemy import func
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


class ExportError(RuntimeError):
    """書き出しの途中で、db の側の辻褄が合わなかった。"""


# ファイル名・ディレクトリ名に使えない字。`/` を含む名前をそのまま置くと
# 階層が一段増えてしまうので、ここで潰す
_UNUSABLE = str.maketrans({c: "_" for c in '\\/:*?"<>|\n\r\t'})


def _safe_name(name: str) -> str:
    """置き場所の一段として使える形に均す。"""
    cleaned = str(name).translate(_UNUSABLE).strip().strip(".")
    return cleaned or "_"


def _record_name(record: MarkdownBase) -> str:
    """ファイル名・ディレクトリ名に使う、レコードの呼び名。"""
    name = getattr(record, "name", None) or getattr(record, "title", None)
    return str(name) if name else f"id{record.id}"


def dump_record_to_markdown(record: MarkdownBase, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(record.text or "")


class _ExportTally:
    """書き出したレコードを数え、同じレコードを二度たどらないよう見張る。"""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.seen: set[tuple[str, int]] = set()

    def mark(self, record: MarkdownBase) -> None:
        key = (record.__tablename__, record.id)
        if key in self.seen:
            raise ExportError(
                f"{record.__tablename__} の id={record.id} を二度たどった。"
                f"親をたどる欄が輪になっている")
        self.seen.add(key)
        self.counts[record.__tablename__] = self.counts.get(record.__tablename__, 0) + 1


class MarkdownExporter:
    """一つのテーブルを md へ書き出す係。

    **テーブルを増やしたら、ここに一つ足して `root_exporters` か
    どこかの `children` に繋ぐ。** 継承関係から拾って勝手に増やさない
    （どのレコードがどこに置かれるかを、この一覧だけで読めるようにする）。

    置き場所は次の規則で決まる:

    - `folder` を親のディレクトリの下に掘り、その中へ書く
    - 子を持ちうるもの（`children` がある・`self_parent_column` がある）は
      自分のディレクトリを持ち、`<名>/<名>.md` に本文を置く。
      子はそのディレクトリの下に入る
    - 子を持たないものは `<名>.md` の一枚で済ませる
    - `stamp_column` があれば、ファイル名の頭に時刻を付ける
      （`4354_09_28_170000_見たことを本人にだけ言う.md`）
    """

    model: type[MarkdownBase]
    folder: str = ""
    # 持ち主（別のテーブル）を指す欄。子の係だけが持つ
    parent_column: str | None = None
    # 同じテーブルの親を指す欄。階層を作るものだけが持つ
    self_parent_column: str | None = None
    # ファイル名の頭に付ける時刻の欄
    stamp_column: str | None = None
    # 自分のディレクトリの下に入る、別テーブルの係
    children: tuple[type["MarkdownExporter"], ...] = ()

    @property
    def has_own_directory(self) -> bool:
        return bool(self.children) or self.self_parent_column is not None

    def load_query(self, parent_id: int | None = None) -> Select:
        """`parent_id` の配下にあるレコードを引く。

        親の欄を持たないテーブル（`kind` `skill`）は全件。持つテーブルは、
        `parent_id` が `None` なら親のいないもの（＝最上段）だけを引く。
        """
        query = select(self.model)
        column_name = self.parent_column or self.self_parent_column
        if column_name is not None:
            column = getattr(self.model, column_name)
            query = query.where(column.is_(None) if parent_id is None else column == parent_id)
        return query.order_by(self.model.id)

    def file_stem(self, record: MarkdownBase) -> str:
        """拡張子を除いたファイル名。"""
        stem = _safe_name(_record_name(record))
        if self.stamp_column is not None:
            stamp = getattr(record, self.stamp_column, None)
            if stamp is not None:
                stem = f"{stamp.stem()}_{stem}"
        return stem

    def export_record(self, record: MarkdownBase, path: str) -> None:
        dump_record_to_markdown(record, path)
        record.filepath = path

    def export(self, s: Session, directory: str,
               parent_id: int | None = None,
               tally: _ExportTally | None = None) -> _ExportTally:
        """`directory` の下に `folder` を掘って、その中へ書き出す。"""
        tally = tally if tally is not None else _ExportTally()
        target = os.path.join(directory, self.folder) if self.folder else directory
        self._export_into(s, target, parent_id, tally)
        return tally

    def _export_into(self, s: Session, directory: str,
                     parent_id: int | None, tally: _ExportTally) -> None:
        records = s.scalars(self.load_query(parent_id)).all()

        # 同じ名前が並んだら、**並んだものすべてに** id を足して分ける。
        # 片方だけに足すと、一件消えたときに残りの名前まで変わってしまう
        stems: dict[int, str] = {r.id: self.file_stem(r) for r in records}
        crowded = {stem for stem in stems.values()
                   if list(stems.values()).count(stem) > 1}
        for record_id, stem in stems.items():
            if stem in crowded:
                stems[record_id] = f"{stem}_id{record_id}"

        for record in records:
            tally.mark(record)
            stem = stems[record.id]

            if self.has_own_directory:
                own_directory = os.path.join(directory, stem)
                self.export_record(record, os.path.join(own_directory, f"{stem}.md"))
            else:
                own_directory = directory
                self.export_record(record, os.path.join(directory, f"{stem}.md"))

            if self.self_parent_column is not None:
                # 同じテーブルの子は、フォルダを挟まずそのまま下に入る
                self._export_into(s, own_directory, record.id, tally)
            for child_class in self.children:
                child_class().export(s, own_directory, record.id, tally)


# ---------------------------------------------------------------- 各テーブル

class CharacterEmotionExporter(MarkdownExporter):
    """人物の情動（drive）。人物のディレクトリの下に置く。"""

    model = CharacterEmotion
    folder = CharacterEmotion.__tablename__
    parent_column = "character_id"
    stamp_column = "start"


class CharacterEventExporter(MarkdownExporter):
    """人物の行動。**行動は出来事の一種で、別表を持たない**（`schema.py`）。"""

    model = Event
    folder = "events"
    parent_column = "character_id"
    stamp_column = "time"


class ObjectEventExporter(MarkdownExporter):
    """個体（群）の行動。"""

    model = Event
    folder = "events"
    parent_column = "object_id"
    stamp_column = "time"

    def load_query(self, parent_id: int | None = None) -> Select:
        # 人物の行動はそちらへ置くので、ここでは拾わない
        return (super().load_query(parent_id)
                .where(Event.character_id.is_(None)))


class EpisodeExporter(MarkdownExporter):
    """話。作品のディレクトリの下、`episodes/` に話数で並べる。"""

    model = Episode
    folder = "episodes"
    parent_column = "story_id"

    def file_stem(self, record: MarkdownBase) -> str:
        # 話数がそのままファイル名になる。**ゼロ埋めしない**（`schema.py`）
        number = getattr(record, "number", None)
        return str(number) if number is not None else f"id{record.id}"


class LocationExporter(MarkdownExporter):
    model = Location
    folder = Location.__tablename__
    self_parent_column = "parent_id"


class TermExporter(MarkdownExporter):
    model = Term
    folder = Term.__tablename__
    self_parent_column = "parent_term_id"


class KindExporter(MarkdownExporter):
    model = Kind
    folder = Kind.__tablename__


class ObjectExporter(MarkdownExporter):
    model = Object
    folder = Object.__tablename__
    children = (ObjectEventExporter,)


class SkillExporter(MarkdownExporter):
    model = Skill
    folder = Skill.__tablename__


class CharacterExporter(MarkdownExporter):
    model = Character
    folder = Character.__tablename__
    children = (CharacterEmotionExporter, CharacterEventExporter)


class StoryExporter(MarkdownExporter):
    model = Story
    folder = Story.__tablename__
    children = (EpisodeExporter,)


class LooseEventExporter(MarkdownExporter):
    """誰の行動でもない、ただ起きたこと。持ち主がいないので直下に置く。"""

    model = Event
    folder = Event.__tablename__
    stamp_column = "time"

    def load_query(self, parent_id: int | None = None) -> Select:
        return (super().load_query(parent_id)
                .where(Event.character_id.is_(None), Event.object_id.is_(None)))


# `worlds/` の直下に立つ係。この順に書き出す。
# 子を持つ係（人物・個体・作品）の下に、情動・行動・話がぶら下がる
root_exporters: tuple[type[MarkdownExporter], ...] = (
    LocationExporter,
    TermExporter,
    KindExporter,
    ObjectExporter,
    SkillExporter,
    CharacterExporter,
    StoryExporter,
    LooseEventExporter,
)

WORLDS_ROOT = "worlds"


def _verify(s: Session, tally: _ExportTally) -> None:
    """**一枚も落とさなかったかを検める。**

    親を指す欄が db にない id を指していたり、親子が輪になっていたりすると、
    そのレコードはどの係からもたどれずに消える。本文が黙って消えるのが
    一番まずいので、数で突き合わせて合わなければ止める。
    """
    models: dict[str, type[MarkdownBase]] = {}
    stack: list[type[MarkdownExporter]] = list(root_exporters)
    while stack:
        exporter_class = stack.pop()
        models[exporter_class.model.__tablename__] = exporter_class.model
        stack.extend(exporter_class.children)

    missing = []
    for table_name, model in models.items():
        total = s.scalar(select(func.count()).select_from(model)) or 0
        written = tally.counts.get(table_name, 0)
        if written != total:
            missing.append(f"{table_name}: {total} 件のうち {written} 件しか書き出せていない")
    if missing:
        raise ExportError(
            "書き出せなかったレコードがある（親を指す欄が実在しない id を"
            "指している／親子が輪になっている）:\n  " + "\n  ".join(missing))


def export_db(root: str = WORLDS_ROOT) -> dict[str, int]:
    """**db の本文をすべて `worlds/` の下へ md として書き出す。**

    db が本体で、`worlds/` はその写し。中途半端に混ざるのを避けるため、
    毎回まるごと消してから書き直す。

    書き出せなかったレコードが一件でもあれば `ExportError` で止まる
    （そのときも書けたところまでは `worlds/` に残る。db は触っていないので、
    db の側を直してから呼び直せばよい）。

    戻り値はテーブル名ごとの件数。
    """
    shutil.rmtree(root, ignore_errors=True)

    tally = _ExportTally()
    with get_session() as s:
        for exporter_class in root_exporters:
            exporter_class().export(s, root, None, tally)
        _verify(s, tally)
        s.commit()
    return tally.counts
