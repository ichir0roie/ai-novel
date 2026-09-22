#!/usr/bin/env python3
from __future__ import annotations

import enum
import os

from sqlalchemy import (
    BigInteger, Boolean, Integer, String, DECIMAL, JSON, TypeDecorator,
    create_engine,
    ForeignKey,
    select,
    Select,
    text,
    update,
    or_,
    and_,
    delete,
)
from sqlalchemy.orm import (
    Session,
    joinedload,
    selectinload,
    lazyload,
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from sqlalchemy import func

from DEM.db.polygon import parse_polygon
from DEM.db.stamp import Stamp


class StampType(TypeDecorator):

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        parsed = Stamp.parse(value)
        if parsed is None:
            raise ValueError(f"Invalid stamp value: {value}")
        return parsed.to_int()

    def process_result_value(self, value, dialect):
        return Stamp.from_int(value)


class PolygonType(TypeDecorator):

    impl = JSON
    cache_ok = True

    def __init__(self):
        # 既定だと None が JSON の 'null' 文字列で入り、IS NULL で引けなくなる
        super().__init__(none_as_null=True)

    def process_bind_param(self, value, dialect):
        return parse_polygon(value)


LOCATION_COLUMNS = ("location_world", "location_planet",
                    "location_longitude", "location_latitude",
                    "location_altitude")

_LOCATION_TAGS = ("w", "p", "lon", "lat", "alt")


def _digit(value) -> str:
    """`4.0` を `4` に寄せて、座標を見た目の揺れなく並べる。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    return str(int(number)) if number == int(number) else repr(number)


def location_text(values) -> str | None:
    """**場所の一意テキスト。** `w/p/lon/lat/alt` を並べて一本の文字列にする。

    `values` は辞書でもレコードの行でもよい。欠けている桁は `-` で埋める。
    どの桁も無ければ `None`(座標を持たない場所)。

    `w4/p1/lon12/lat-/alt-` のように、上から順に並ぶ。前方一致がそのまま
    「同じ世界線」「同じ星」の絞り込みになる。
    """
    get = values.get if hasattr(values, "get") else (
        lambda column: getattr(values, column, None))
    parts = [get(column) for column in LOCATION_COLUMNS]
    if all(part in (None, "") for part in parts):
        return None
    return "/".join(
        tag + ("-" if part in (None, "") else _digit(part))
        for tag, part in zip(_LOCATION_TAGS, parts))


class Base(DeclarativeBase):

    # SQLite は「INTEGER PRIMARY KEY」だけを rowid の別名として autoincrement する。
    # Integer だと型名が INTEGER と一致せず insert のたびに id が NULL のまま失敗する。
    # sort_order は列の並び順を明示するための番号。継承の段が一段深くなるごとに
    # 開始値を 100 増やし、同じクラス内では 10 刻みで振る(あとで列を挟みやすい)。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, sort_order=0)


class MarkdownBase(Base):
    __abstract__ = True

    text: Mapped[str] = mapped_column(String,  nullable=False, sort_order=10000)

    directory_path: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None, sort_order=20000,
        comment="import,export時の配置先。worlds/{table}/ からの相対ディレクトリパス。"
                "空ならテーブル直下に置く")
    filename: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None, sort_order=20010,
        comment="import,export時のファイル名(id・拡張子を除いた部分)。"
                "空なら {id}.md。テーブルが持つ name 等の列とは別物")


class Location(MarkdownBase):

    __tablename__ = "location"

    name: Mapped[str | None] = mapped_column(String, sort_order=200)
    kind: Mapped[str | None] = mapped_column(String, sort_order=210)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("location.id"), sort_order=220)

    # 位置は**一つの座標系だけ**で持つ。経度・緯度・高度で持ち、
    # **どこを原点とするかは星ごとに決めて、その星の md に書く**。
    location_world: Mapped[float | None] = mapped_column(DECIMAL, comment="世界線番号 W", sort_order=230)
    location_planet: Mapped[int | None] = mapped_column(Integer, comment="惑星番号 P", sort_order=240)
    location_longitude: Mapped[float | None] = mapped_column(DECIMAL, comment="経度。基準の子午線から東へ何度(西は負)", sort_order=250)
    location_latitude: Mapped[float | None] = mapped_column(DECIMAL, comment="緯度。赤道から北へ何度(南は負)", sort_order=260)
    location_altitude: Mapped[float | None] = mapped_column(DECIMAL, comment="高度。基準面から上へ何 m", sort_order=270)
    polygon: Mapped[dict | None] = mapped_column(
        PolygonType, comment="輪郭。GeoJSON の Polygon(`coordinates` は [経度, 緯度] の環の並び、"
        "先頭が外周で以降は穴)。地図では面として描く。経緯度が無くても持てる", sort_order=280)

    area: Mapped[float | None] = mapped_column(
        DECIMAL, comment="広さ。単位は決めていないが、親と子で揃える。"
        "子の広さは親未満、兄弟(同じ parent_id)を足しても親を超えない", sort_order=290)
    environment: Mapped[str | None] = mapped_column(String, comment="環境", sort_order=300)

    sample_region: Mapped[str | None] = mapped_column(
        String, comment="参考にした実在の地域(例: 「北欧」「地中海沿岸」)。"
        "固有名詞をそのまま使うのではなく、地理・気候・景観の手がかりとして持つ", sort_order=305)
    sample_culture: Mapped[str | None] = mapped_column(
        String, comment="参考にした実在の文化(例: 「遊牧」「稲作」)。"
        "風習・生活様式・価値観の手がかりとして持つ", sort_order=307)
    sample_era: Mapped[str | None] = mapped_column(
        String, comment="参考にした実在の時代(例: 「中世」「産業革命期」)。"
        "技術水準・社会制度の手がかりとして持つ", sort_order=308)

    start: Mapped[Stamp | None] = mapped_column(StampType, sort_order=310)
    end: Mapped[Stamp | None] = mapped_column(StampType, sort_order=320)

    active_random_generation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 自分の親(一つ上の場所)。木をのぼって道筋(place_path)を組むのに使う。
    # 書き込みは常に parent_id を直に触るので、どちらも読み取り専用にしておく
    # (viewonly を外すと、同じ外部キーを double-write しようとして SQLAlchemy が警告する)。
    parent: Mapped["Location | None"] = relationship(
        remote_side="Location.id", viewonly=True, lazy="noload")
    children: Mapped[list[Location]] = relationship(viewonly=True)


class Event(MarkdownBase):

    __tablename__ = "event"

    name: Mapped[str] = mapped_column(String, sort_order=200)
    # 断面(ReadBrief)に出すかどうかだけを持つ。分類は name/text の書き方で表す。
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, sort_order=210)
    time: Mapped[Stamp] = mapped_column(StampType, index=True, sort_order=220)

    parent_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("event.id"), sort_order=230)

    location_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("location.id"), index=True, sort_order=240)
    location: Mapped[Location | None] = relationship(lazy="noload")

    # 行動もここに入る(人物の行動に別表は無い)。誰の行動かは
    # event_character(中間テーブル、多対多)が持つ。空なら
    # 誰の行動でもない「ただ起きたこと」。
    event_characters: Mapped[list["EventCharacter"]] = relationship(
        back_populates="event", lazy="noload", cascade="all, delete-orphan")

    start: Mapped[Stamp | None] = mapped_column(StampType, sort_order=250)
    end: Mapped[Stamp | None] = mapped_column(StampType, sort_order=260)

    parent_event: Mapped["Event | None"] = relationship(
        remote_side="Event.id", back_populates="child_events", lazy="noload"
    )
    child_events: Mapped[list["Event"]] = relationship(
        back_populates="parent_event", lazy="noload", cascade="all, delete-orphan"
    )


class EventCharacter(Base):
    """**出来事 ↔ 人物の中間テーブル。** 一つの出来事に何人でも掛かれる。"""

    __tablename__ = "event_character"

    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("event.id"), index=True, sort_order=100)
    character_id: Mapped[int] = mapped_column(Integer, ForeignKey("character.id"), index=True, sort_order=110)

    event: Mapped["Event"] = relationship(back_populates="event_characters", lazy="noload")
    character: Mapped["Character"] = relationship(lazy="noload")


class Plot(MarkdownBase):
    """その場所の出来事生成に指示したい筋書き。"""

    __tablename__ = "plot"

    location_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("location.id"), index=True,
        comment="この筋書きが掛かる場所", sort_order=100)
    location: Mapped["Location | None"] = relationship(lazy="noload")

    start: Mapped[Stamp | None] = mapped_column(StampType, nullable=True)
    end: Mapped[Stamp | None] = mapped_column(StampType, nullable=True)


CHARACTER_KIND_PERSON = "人物"


class PersonalityLevel(enum.StrEnum):
    """性格の各軸の段階。列には値(「無」など)をそのまま文字列で持つ。"""

    NONE = "無"
    LOW = "低"
    NORMAL = "並"
    HIGH = "高"
    MUST = "必"


PERSONALITY_LEVELS = tuple(level.value for level in PersonalityLevel)
PERSONALITY_DEFAULT = PersonalityLevel.NORMAL.value

PERSONALITY_COLUMNS = (
    "sincerity", "curiosity", "proactivity", "cooperativeness", "sociability",
    "emotional_expression", "self_esteem", "self_efficacy", "stress_resilience",
    "flexibility_of_values", "sensitivity", "imagination",
)


def check_personality(data) -> None:
    """辞書に入っている性格の欄が `PERSONALITY_LEVELS` のどれかであることを確かめる。"""
    bad = {column: data[column] for column in PERSONALITY_COLUMNS
           if column in data and data[column] not in PERSONALITY_LEVELS}
    if bad:
        raise ValueError(
            f"性格は {'/'.join(PERSONALITY_LEVELS)} のいずれか: {bad}")


class Character(MarkdownBase):
    """出来事の当事者になるもの。人物に限らず、国・組織・集団・物も一行として持つ(`kind` で区別)。"""

    __tablename__ = "character"

    text: Mapped[str | None] = mapped_column(String, nullable=True, sort_order=10000)

    name: Mapped[str | None] = mapped_column(String, sort_order=210)
    read: Mapped[str | None] = mapped_column(String, sort_order=220)
    kind: Mapped[str] = mapped_column(
        String, default=CHARACTER_KIND_PERSON, nullable=False,
        comment="種別。「人物」か、人物以外の対象(国・組織・商会・氏族・集団・物など)", sort_order=230)

    start: Mapped[Stamp | None] = mapped_column(StampType, sort_order=250)
    end: Mapped[Stamp | None] = mapped_column(StampType, sort_order=260)

    # 出自(生まれの場所)は別列を持たず、CharacterPlace の一番古い行として表す。
    # 体格・口調は人物だけが持つ。人物以外の対象は空のまま。
    # --- 体格 -------------------------------------------------------------
    sex: Mapped[str | None] = mapped_column(String,  comment="性別", sort_order=320)
    height: Mapped[float | None] = mapped_column(DECIMAL, comment="背丈 cm", sort_order=330)
    build: Mapped[str | None] = mapped_column(String,  comment="体格", sort_order=340)

    # --- 口調 -------------------------------------------------------------
    first_person: Mapped[str | None] = mapped_column(String,  comment="一人称", sort_order=350)
    second_person: Mapped[str | None] = mapped_column(String,  comment="二人称", sort_order=360)
    third_person: Mapped[str | None] = mapped_column(String,  comment="三人称", sort_order=370)
    tone: Mapped[str | None] = mapped_column(String,  comment="口調", sort_order=380)

    # --- 性格 -----------------------------------------------------------
    # 各列は PersonalityLevel の値(無/低/並/高/必)。
    sincerity: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="誠実性", sort_order=390)
    curiosity: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="好奇心", sort_order=400)
    proactivity: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="行動力", sort_order=410)
    cooperativeness: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="協調性", sort_order=420)
    sociability: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="社交性", sort_order=430)
    emotional_expression: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="感情表現", sort_order=440)
    self_esteem: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="自己肯定感", sort_order=450)
    self_efficacy: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="自己効力感", sort_order=460)
    stress_resilience: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="ストレス耐性", sort_order=470)
    flexibility_of_values: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="価値観の柔軟性", sort_order=480)
    sensitivity: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="感受性", sort_order=490)
    imagination: Mapped[str] = mapped_column(String, default=PERSONALITY_DEFAULT, nullable=False, comment="想像力", sort_order=500)

    # relationships

    places: Mapped[list[CharacterPlace]] = relationship(
        back_populates="character", lazy="noload", order_by="CharacterPlace.start.desc()"
    )
    plots: Mapped[list[CharacterPlot]] = relationship(
        back_populates="character", lazy="noload", order_by="CharacterPlot.start.desc()")

    events: Mapped[list[Event]] = relationship(
        secondary="event_character", viewonly=True, lazy="noload",
        order_by="Event.start.desc()"
    )


class CharacterPlace(Base):

    __tablename__ = "character_place"

    character_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("character.id"), sort_order=100)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("location.id"), sort_order=110)

    start: Mapped[Stamp | None] = mapped_column(StampType, sort_order=120)
    end: Mapped[Stamp | None] = mapped_column(StampType, sort_order=130)

    character: Mapped[Character | None] = relationship(back_populates="places", lazy="noload")
    place: Mapped[Location] = relationship(lazy="noload")


class CharacterPlot(MarkdownBase):
    """その人物の出来事生成に指示したい筋書き。`Plot`(場所側)の人物版。"""

    __tablename__ = "character_plot"

    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("character.id"), index=True,
        comment="この筋書きが掛かる人物", sort_order=100)
    character: Mapped["Character"] = relationship(back_populates="plots", lazy="noload")

    start: Mapped[Stamp | None] = mapped_column(StampType, nullable=True)
    end: Mapped[Stamp | None] = mapped_column(StampType, nullable=True)


class CharacterRelation(MarkdownBase):
    """人物同士の相関。`character_id_1` から見た `character_id_2` との関係を一行で持つ。"""

    __tablename__ = "character_relation"

    character_id_1: Mapped[int] = mapped_column(
        Integer, ForeignKey("character.id"), index=True,
        comment="関係の主体となる人物", sort_order=100)
    character_id_2: Mapped[int] = mapped_column(
        Integer, ForeignKey("character.id"), index=True,
        comment="関係の相手となる人物", sort_order=110)
    relation: Mapped[str] = mapped_column(
        String, nullable=False, comment="関係の短い名前(母・師・宿敵 など)", sort_order=120)

    character_1: Mapped["Character"] = relationship(
        foreign_keys="CharacterRelation.character_id_1", lazy="noload")
    character_2: Mapped["Character"] = relationship(
        foreign_keys="CharacterRelation.character_id_2", lazy="noload")


class Term(MarkdownBase):
    __tablename__ = "term"

    name: Mapped[str] = mapped_column(String, sort_order=200)
    kind: Mapped[str] = mapped_column(String, sort_order=210)

    restrict_world_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("location.id"), sort_order=220)
    restrict_planet_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("location.id"), sort_order=230)
    restrict_place_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("location.id"), sort_order=240)

    parent_term_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("term.id"), comment="上位の語。置いたディレクトリで決まる", sort_order=250)


class Story(MarkdownBase):

    __tablename__ = "story"

    name: Mapped[str] = mapped_column(String, sort_order=200)

    world_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("location.id"), comment="使用する世界線", sort_order=210)
    world: Mapped[Location | None] = relationship(
        foreign_keys="Story.world_id", lazy="noload")
    place_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("location.id"), comment="立つ場所。断面を取るのに使う", sort_order=220)
    place: Mapped[Location | None] = relationship(
        foreign_keys="Story.place_id", lazy="noload")
    narration: Mapped[str] = mapped_column(String,  comment="語り", sort_order=230)
    state: Mapped[str] = mapped_column(String,  comment="状態", sort_order=240)

    start: Mapped[Stamp | None] = mapped_column(StampType, comment="立つ年", sort_order=250)
    end: Mapped[Stamp | None] = mapped_column(StampType, sort_order=260)

    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="story", lazy="noload", order_by="Episode.number.asc()")


class Episode(MarkdownBase):

    __tablename__ = "episode"

    story_id: Mapped[int] = mapped_column(Integer, ForeignKey("story.id"), sort_order=200)
    story: Mapped[Story] = relationship(back_populates="episodes", lazy="noload")
    number: Mapped[int | None] = mapped_column(
        Integer, comment="話数。ファイル名の数がそのまま入る。**ゼロ埋めしない**", sort_order=210)
    title: Mapped[str] = mapped_column(
        String,  comment="サブタイトル。本文の見出しから読む", sort_order=220)
    letters: Mapped[int | None] = mapped_column(Integer, comment="字数", sort_order=230)
    synced: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="同期フラグ。この話の出来事・行動が台帳へ戻してあるか。"
                "自動生成時はオン、手で書いたときはオフ。"
                "オフの話があるあいだは、次の話の材料を読み出せない",
        sort_order=240)


DB_PATH = os.environ.get("DEM_DB_PATH", "novel.db")


def create_db(path=DB_PATH):
    """**db ファイルを作り直して、空のテーブルを張る。**

    台帳から何度でも組み直せるので、既にあれば消して作り直す。
    """
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        # sqlite の既定も UTF-8 だが、文字化け事故を防ぐため明記しておく。
        # テーブルが空のうちしか効かないので create_all の前に打つ。
        conn.execute(text("PRAGMA encoding='UTF-8'"))
    Base.metadata.create_all(engine)
    return engine


NOVEL_DB_PATH = "novel.db"
TEST_DB_PATH = "novel.test.db"


def _make_engine(path):
    return create_engine(f"sqlite:///{os.path.abspath(path)}")


engine = _make_engine(DB_PATH)
_fixed_engines = {}


def _fixed_engine(path):
    if path not in _fixed_engines:
        _fixed_engines[path] = _make_engine(path)
    return _fixed_engines[path]


def get_env_session():
    """`DEM_DB_PATH`(既定は novel.db)の db。普段の読み書きはこれ。"""
    return Session(engine)


def get_novel_session():
    """環境変数に関わらず本番の novel.db。`worlds/` との同期(import_db / export_db)用。"""
    return Session(_fixed_engine(NOVEL_DB_PATH))


def get_test_session():
    """環境変数に関わらず novel.test.db。"""
    return Session(_fixed_engine(TEST_DB_PATH))
