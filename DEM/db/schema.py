#!/usr/bin/env python3
from __future__ import annotations

import os

from sqlalchemy import (
    BigInteger, Boolean, Integer, String, DECIMAL, TypeDecorator,
    create_engine,
    ForeignKey,
    select,
    Select,
    update,
    or_,
    and_
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
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class MarkdownBase(Base):
    __abstract__ = True

    text: Mapped[str] = mapped_column(String,  nullable=False)

    filepath: Mapped[str | None] = mapped_column(String, nullable=True, default=None)


class Location(MarkdownBase):

    __tablename__ = "location"

    name: Mapped[str | None] = mapped_column(String)
    kind: Mapped[str | None] = mapped_column(String)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("location.id"))

    # 位置は**一つの座標系だけ**で持つ。経度・緯度・高度で持ち、
    # **どこを原点とするかは星ごとに決めて、その星の md に書く**。
    location_world: Mapped[float | None] = mapped_column(DECIMAL, comment="世界線番号 W")
    location_planet: Mapped[int | None] = mapped_column(Integer, comment="惑星番号 P")
    location_longitude: Mapped[float | None] = mapped_column(
        DECIMAL, comment="経度。基準の子午線から東へ何度(西は負)")
    location_latitude: Mapped[float | None] = mapped_column(
        DECIMAL, comment="緯度。赤道から北へ何度(南は負)")
    location_altitude: Mapped[float | None] = mapped_column(
        DECIMAL, comment="高度。基準面から上へ何 m")

    location_key: Mapped[str | None] = mapped_column(
        String, unique=True, index=True,
        comment="場所の一意テキスト。`w/p/lon/lat/alt` を並べて文字列にしたもの。"
                "md には書かない。読み込みのときに組み立てる(location_text)")

    area: Mapped[float | None] = mapped_column(
        DECIMAL, comment="広さ。単位は決めていないが、親と子で揃える。"
        "子の広さは親未満、兄弟(同じ parent_id)を足しても親を超えない")
    environment: Mapped[str | None] = mapped_column(String, comment="環境")

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)

    # 自分の親(一つ上の場所)。木をのぼって道筋(place_path)を組むのに使う。
    parent: Mapped["Location | None"] = relationship(remote_side="Location.id", lazy="noload")
    children: Mapped[list[Location]] = relationship()


class LocationResource(MarkdownBase):
    """**場所に紐づく資源。** `start` 時点で `quantity`(総量)、`end` 時点で 0 になるよう、
    その間を線形に減らしていく前提で持つ(`resource_amount_at` で時点の量を計算する)。
    """

    __tablename__ = "location_resource"

    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("location.id"), index=True)
    location: Mapped["Location"] = relationship(lazy="noload")

    kind: Mapped[str] = mapped_column(String, comment="種別")
    quantity: Mapped[int] = mapped_column(Integer, comment="総量。start 時点の量")
    unit: Mapped[str] = mapped_column(String, comment="単位")

    start: Mapped[Stamp] = mapped_column(StampType, comment="この量を数え始める時刻。総量ぶんある")
    end: Mapped[Stamp] = mapped_column(StampType, comment="尽きる時刻。0になる")


def resource_amount_at(resource: LocationResource, time) -> float:
    """`resource` の、`time` 時点での残量。

    `start` 時点で `quantity`(総量)、`end` 時点で 0 になるよう、その間を
    線形に減らす。範囲の外なら両端の値(`quantity` / `0`)で止める。
    """
    at = Stamp.parse(time)
    if at <= resource.start:
        return float(resource.quantity)
    if at >= resource.end:
        return 0.0
    total_span = resource.end.to_seconds() - resource.start.to_seconds()
    elapsed = at.to_seconds() - resource.start.to_seconds()
    return resource.quantity * (1 - elapsed / total_span)


class Event(MarkdownBase):

    __tablename__ = "event"

    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="")
    time: Mapped[Stamp] = mapped_column(StampType, index=True)

    parent_event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("event.id"))

    place_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("location.id"), index=True)
    place: Mapped[Location | None] = relationship(lazy="noload")

    # **行動もここに入る。** 人物・個体の行動は別表を持たない。
    # 誰の行動かは `event_character` `event_object`(中間テーブル)が持つ。
    # 掛かり先の出来事は `parent_event_id`。どちらも空なら、
    # 誰の行動でもない「ただ起きたこと」。人物・個体は**それぞれ何人・何個体でも**
    # 掛かれる(多対多)
    event_characters: Mapped[list["EventCharacter"]] = relationship(
        back_populates="event", lazy="noload", cascade="all, delete-orphan")
    event_objects: Mapped[list["EventObject"]] = relationship(
        back_populates="event", lazy="noload", cascade="all, delete-orphan")

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)

    parent_event: Mapped["Event | None"] = relationship(
        remote_side="Event.id", back_populates="child_events", lazy="noload"
    )
    child_events: Mapped[list["Event"]] = relationship(
        back_populates="parent_event", lazy="noload", cascade="all, delete-orphan"
    )


class EventCharacter(Base):
    """**出来事 ↔ 人物の中間テーブル。** 一つの出来事に何人でも掛かれる。"""

    __tablename__ = "event_character"

    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("event.id"), index=True)
    character_id: Mapped[int] = mapped_column(Integer, ForeignKey("character.id"), index=True)

    event: Mapped["Event"] = relationship(back_populates="event_characters", lazy="noload")
    character: Mapped["Character"] = relationship(lazy="noload")


class EventObject(Base):
    """**出来事 ↔ 個体(群)の中間テーブル。** 一つの出来事に何個体でも掛かれる。"""

    __tablename__ = "event_object"

    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("event.id"), index=True)
    object_id: Mapped[int] = mapped_column(Integer, ForeignKey("object.id"), index=True)

    event: Mapped["Event"] = relationship(back_populates="event_objects", lazy="noload")
    object: Mapped["Object"] = relationship(lazy="noload")


class Kind(MarkdownBase):

    __tablename__ = "kind"

    name: Mapped[str] = mapped_column(String)
    read: Mapped[str] = mapped_column(String)


class ObjectBase:
    root_place_name: Mapped[int | None] = mapped_column(Integer, ForeignKey("location.id"))

    name: Mapped[str | None] = mapped_column(String)
    read: Mapped[str | None] = mapped_column(String)

    kind_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("kind.id"))

    world_influence: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="世界線への影響度。大きいほど世界線を変える")

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Object(MarkdownBase, ObjectBase):
    __tablename__ = "object"

    kind: Mapped["Kind | None"] = relationship(lazy="noload")


class ObjectPlace(Base):
    __tablename__ = "object_place"

    object_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("object.id"))
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("location.id"))

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)

    object: Mapped["Object | None"] = relationship(lazy="noload")
    place: Mapped[Location] = relationship(lazy="noload")


class Character(MarkdownBase, ObjectBase):

    __tablename__ = "character"

    # --- 出自 -------------------------------------------------------------
    born_place_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("location.id"))
    born_place: Mapped[Location | None] = relationship(
        foreign_keys="Character.born_place_id", lazy="noload")
    belong_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("object.id"), comment="所属。個体のどれか")
    belong: Mapped["Object | None"] = relationship(lazy="noload")

    # --- 体格 -------------------------------------------------------------
    sex: Mapped[str] = mapped_column(String,  comment="性別")
    height: Mapped[float | None] = mapped_column(DECIMAL, comment="背丈 cm")
    build: Mapped[str] = mapped_column(String,  comment="体格")

    # --- 口調 -------------------------------------------------------------
    first_person: Mapped[str] = mapped_column(String,  comment="一人称")
    second_person: Mapped[str] = mapped_column(String,  comment="二人称")
    third_person: Mapped[str] = mapped_column(String,  comment="三人称")
    tone: Mapped[str] = mapped_column(String,  comment="口調")

    # --- 性格 -----------------------------------------------------------
    sincerity: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="誠実性")
    curiosity: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="好奇心")
    proactivity: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="行動力")
    cooperativeness: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="協調性")
    sociability: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="社交性")
    emotional_expression: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="感情表現")
    self_esteem: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="自己肯定感")
    self_efficacy: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="自己効力感")
    stress_resilience: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="ストレス耐性")
    flexibility_of_values: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="価値観の柔軟性")
    sensitivity: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="感受性")
    imagination: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="想像力")

    # relationships

    kind: Mapped["Kind | None"] = relationship(lazy="noload")

    places: Mapped[list[CharacterPlace]] = relationship(
        back_populates="character", lazy="noload", order_by="CharacterPlace.start.desc()"
    )
    skills: Mapped[list[CharacterSkill]] = relationship(
        lazy="noload",  order_by="CharacterSkill.id.asc()")
    emotions: Mapped[list[CharacterEmotion]] = relationship(
        lazy="noload",  order_by="CharacterEmotion.start.desc()")

    events: Mapped[list[Event]] = relationship(
        secondary="event_character", viewonly=True, lazy="noload",
        order_by="Event.start.desc()"
    )


class CharacterPlace(Base):

    __tablename__ = "character_place"

    character_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("character.id"))
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("location.id"))

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)

    character: Mapped[Character | None] = relationship(back_populates="places", lazy="noload")
    place: Mapped[Location] = relationship(lazy="noload")


class Skill(MarkdownBase):

    __tablename__ = "skill"

    name: Mapped[str] = mapped_column(String)

    # 現象、コスト、効果、範囲、持続時間、対象、条件、制約
    cost: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="コスト")
    effect: Mapped[str] = mapped_column(String, nullable=False, comment="効果")
    range: Mapped[str] = mapped_column(String, comment="範囲")
    duration: Mapped[str] = mapped_column(String, comment="持続時間")
    target: Mapped[str] = mapped_column(String, comment="対象")
    constraint: Mapped[str] = mapped_column(String,  comment="制約")


class CharacterSkill(Base):

    __tablename__ = "character_skill"

    character_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("character.id"))
    object_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("object.id"))

    skill_id: Mapped[int] = mapped_column(Integer, ForeignKey("skill.id"), nullable=False)
    skill: Mapped["Skill"] = relationship(lazy="noload")

    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="熟練度")


class CharacterEmotion(MarkdownBase):

    __tablename__ = "character_drive"

    character_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("character.id"))

    text: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Term(MarkdownBase):
    __tablename__ = "term"

    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)

    restrict_world_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("location.id"))
    restrict_planet_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("location.id"))
    restrict_place_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("location.id"))

    parent_term_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("term.id"), comment="上位の語。置いたディレクトリで決まる")


class Story(MarkdownBase):

    __tablename__ = "story"

    name: Mapped[str] = mapped_column(String)

    world_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("location.id"), comment="使用する世界線")
    world: Mapped[Location | None] = relationship(
        foreign_keys="Story.world_id", lazy="noload")
    place_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("location.id"), comment="立つ場所。断面を取るのに使う")
    place: Mapped[Location | None] = relationship(
        foreign_keys="Story.place_id", lazy="noload")
    narration: Mapped[str] = mapped_column(String,  comment="語り")
    state: Mapped[str] = mapped_column(String,  comment="状態")

    start: Mapped[Stamp | None] = mapped_column(StampType, comment="立つ年")
    end: Mapped[Stamp | None] = mapped_column(StampType)

    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="story", lazy="noload", order_by="Episode.number.asc()")


class Episode(MarkdownBase):

    __tablename__ = "episode"

    story_id: Mapped[int] = mapped_column(Integer, ForeignKey("story.id"))
    story: Mapped[Story] = relationship(back_populates="episodes", lazy="noload")
    number: Mapped[int | None] = mapped_column(
        Integer, comment="話数。ファイル名の数がそのまま入る。**ゼロ埋めしない**")
    title: Mapped[str] = mapped_column(
        String,  comment="サブタイトル。本文の見出しから読む")
    letters: Mapped[int | None] = mapped_column(Integer, comment="字数")
    synced: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="同期フラグ。この話の出来事・行動が台帳へ戻してあるか。"
                "自動生成時はオン、手で書いたときはオフ。"
                "オフの話があるあいだは、次の話の材料を読み出せない")


DB_PATH = os.environ.get("DEM_DB_PATH", "novel.db")


def create_db(path=DB_PATH):
    """**db ファイルを作り直して、空のテーブルを張る。**

    台帳から何度でも組み直せるので、既にあれば消して作り直す。
    """
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    return engine


engine = create_engine(f"sqlite:///{os.path.abspath(DB_PATH)}", future=True)


def get_session():
    return Session(engine)
