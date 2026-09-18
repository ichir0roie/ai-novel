#!/usr/bin/env python3
from __future__ import annotations

import os

from sqlalchemy import (
    BigInteger, Boolean, Integer, String, DECIMAL, TypeDecorator,
    create_engine, ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from stamp import Stamp


class StampType(TypeDecorator):
    """作中の時刻。**桁を並べた整数として持つ。**
    python の `datetime` は 9999 年までしか持てず、作中の暦はそれを越える。
    `tools/stamp.py` の `Stamp` を、`年月日時分秒` を並べた整数へ落として入れる。
    並びがそのまま時の前後になるので、`ORDER BY` も `<` もそのまま効く。
    """

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
                    "location_x", "location_y", "location_z")

_LOCATION_TAGS = ("w", "p", "x", "y", "z")


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
    どの桁も無ければ `None`（座標を持たない場所）。

    `w4/p1/lon-/lat-/alt-` のように、上から順に並ぶ。前方一致がそのまま
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
    text: Mapped[str] = mapped_column(String, default="", nullable=False)

    id: Mapped[str] = mapped_column(
        String, primary_key=True,
        comment="主キー。md には書かない。読み込むときに上位のレコードの id と名から採番する")


class Place(Base):
    """
    novels/worlds/{place_name}/**/{place_name}.md
    """

    __tablename__ = "place"

    name: Mapped[str | None] = mapped_column(String)
    kind: Mapped[str | None] = mapped_column(String)
    parent_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))

    # 位置は**一つの座標系だけ**で持つ。緯度・経度・高度は持たない
    # （星ごとに基準が変わり、上の場所と突き合わせられないため）。
    location_world: Mapped[float | None] = mapped_column(DECIMAL, comment="世界線番号 W")
    location_planet: Mapped[int | None] = mapped_column(Integer, comment="惑星番号 P")
    location_longitude: Mapped[float | None] = mapped_column(DECIMAL, comment="経度 X")
    location_latitude: Mapped[float | None] = mapped_column(DECIMAL, comment="緯度 Y")
    location_altitude: Mapped[float | None] = mapped_column(DECIMAL, comment="高度 Z")

    location_key: Mapped[str | None] = mapped_column(
        String, unique=True, index=True,
        comment="場所の一意テキスト。`w/p/lon/lat/alt` を並べて文字列にしたもの。"
                "md には書かない。読み込みのときに組み立てる（location_text）")

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Event(Base):
    """
    novels/worlds/{place_name}/**/events/{yyyymmddhhmmss}_{event_name}.md
    novels/objects/{world_name}/**/{object_name}/events/{yyyymmddhhmmss}_{action_name}.md
    novels/characters/{born_place_name}/**/{character_name}/events/{yyyymmddhhmmss}_{action_name}.md

    **起きたことは、ぜんぶここに入る。** 場所で起きたことも、人物・個体が
    したことも同じ表。行動は `character_id` / `object_id` が誰かを持ち、
    掛かり先の出来事を `parent_event_id` が指す。
    ある時刻・ある場所の要素は `place` と結んで一度に引ける。
    """

    __tablename__ = "event"

    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="")
    time: Mapped[Stamp] = mapped_column(StampType, index=True)

    parent_event_id: Mapped[str | None] = mapped_column(String, ForeignKey("event.id"))

    place_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("place.id"), index=True)
    place: Mapped[Place | None] = relationship(lazy="noload")

    # **行動もここに入る。** 人物・個体の行動は別表を持たない。
    # 誰の行動かをこの二つが持ち、掛かり先の出来事は `parent_event_id`。
    # どちらも空なら、誰の行動でもない「ただ起きたこと」。
    character_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("character.id"), index=True,
        comment="その行動をした人物")
    object_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("object.id"), index=True,
        comment="その行動をした個体（群）")

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)

    parent_event: Mapped["Event | None"] = relationship(
        remote_side="Event.id", back_populates="child_events", lazy="noload"
    )
    child_events: Mapped[list["Event"]] = relationship(
        back_populates="parent_event", lazy="selectin", cascade="all, delete-orphan"
    )


class Kind(Base):
    """
    novels/objects/{root_place_name}/{kind_name}.md

    **型。** 何であるかの分類（系統・国・組織・仕組み）。
    個体はこの型にぶら下がる。
    """

    __tablename__ = "kind"

    name: Mapped[str] = mapped_column(String)
    read: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)

    root_place_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Object(Base):
    """
    novels/objects/{world_name}/**/{object_name}/{object_name}.md

    **種族・組織・仕組みなど、まとまりとして振る舞うもの。**
    一人ひとりの人間は `Character` が持つ。ここは群としての行動を持つ。
    """
    __tablename__ = "object"

    root_place_name: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))

    name: Mapped[str] = mapped_column(String)
    read: Mapped[str] = mapped_column(String)

    kind_id: Mapped[str] = mapped_column(String, ForeignKey("kind.id"))
    kind: Mapped[str] = mapped_column(String)

    world_influence: Mapped[int | None] = mapped_column(
        Integer, comment="世界影響力。この個体が世界の動きにどれだけ関わるかの重み")

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)


class ObjectPlace(Base):
    """
    {object_name}/places/{yyyymmddhhmmss}_{place_name}.md
    """

    __tablename__ = "object_place"

    object_id: Mapped[str] = mapped_column(String, ForeignKey("object.id"))
    place_id: Mapped[str] = mapped_column(String, ForeignKey("place.id"))

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Character(Base):
    """
    novels/characters/{born_place_name}/**/{character_name}/{character_name}.md

    **一人ひとりの人間。** 本文で一人称・二人称・三人称を書き分けるために、
    ここがいちばん細かい。群としての振る舞いは `Object` の側にある。
    """

    __tablename__ = "character"

    name: Mapped[str] = mapped_column(String)
    read: Mapped[str] = mapped_column(String)

    born_place_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))
    race_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("kind.id"), comment="種族。種別のどれか")
    belong_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("object.id"), comment="所属。個体のどれか")

    # --- 体 -------------------------------------------------------------
    sex: Mapped[str] = mapped_column(String, default="", comment="性別")
    height: Mapped[float | None] = mapped_column(DECIMAL, comment="背丈 cm")
    build: Mapped[str] = mapped_column(String, default="", comment="体格")
    looks: Mapped[str] = mapped_column(String, default="", comment="見た目の要点")

    # --- 口 -------------------------------------------------------------
    first_person: Mapped[str] = mapped_column(String, default="", comment="一人称")
    second_person: Mapped[str] = mapped_column(String, default="", comment="二人称")
    third_person: Mapped[str] = mapped_column(
        String, default="", comment="三人称。地の文がこの人物を指す呼び方")
    tone: Mapped[str] = mapped_column(String, default="", comment="口調")

    # --- 中身 -----------------------------------------------------------
    personality: Mapped[str] = mapped_column(String, default="", comment="性格")
    emotion: Mapped[str] = mapped_column(
        String, default="", comment="感情。何に揺れるか")
    thought: Mapped[str] = mapped_column(String, default="", comment="思想")
    desire: Mapped[str] = mapped_column(String, default="", comment="欲。自覚した目的")
    lie: Mapped[str] = mapped_column(String, default="", comment="嘘。誤った思い込み")
    need: Mapped[str] = mapped_column(String, default="", comment="必要。本当に要るもの")
    fear: Mapped[str] = mapped_column(String, default="", comment="恐れ")

    # --- できること -----------------------------------------------------
    ability: Mapped[str] = mapped_column(String, default="", comment="能力")
    cost: Mapped[str] = mapped_column(
        String, default="", comment="能力の代償・制限。**制限のない能力は書かない**")

    world_influence: Mapped[int | None] = mapped_column(
        Integer, comment="世界影響力。この人物が世界の動きにどれだけ関わるかの重み")

    start: Mapped[Stamp | None] = mapped_column(StampType, comment="生")
    end: Mapped[Stamp | None] = mapped_column(StampType, comment="没")


class CharacterPlace(Base):
    """
    {character_name}/places/{yyyymmddhhmmss}_{place_name}.md
    """

    __tablename__ = "character_place"

    character_id: Mapped[str] = mapped_column(String, ForeignKey("character.id"))
    place_id: Mapped[str] = mapped_column(String, ForeignKey("place.id"))

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Term(Base):
    """
    novels/terms/**/{term_name}/{term_name}.md

    **入れ子。** ディレクトリが上下を表す。`{term_name}/{term_name}.md` がその語、
    その下のディレクトリがその語にぶら下がる語。
    """
    __tablename__ = "term"

    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)

    restrict_world_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))
    restrict_planet_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))
    restrict_place_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))

    parent_term_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("term.id"), comment="上位の語。置いたディレクトリで決まる")


class Story(Base):
    """
    novels/stories/{story_name}/meta.md

    **作品。** 本文の入れ物。どの世界線のどこに立つかをここが持つ。
    作品は世界線をまたがない。
    """

    __tablename__ = "story"

    name: Mapped[str] = mapped_column(String)

    world_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("place.id"), comment="使用する世界線")
    place_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("place.id"), comment="立つ場所。断面を取るのに使う")
    narration: Mapped[str] = mapped_column(String, default="", comment="語り")
    state: Mapped[str] = mapped_column(String, default="", comment="状態")

    start: Mapped[Stamp | None] = mapped_column(StampType, comment="立つ年")
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Episode(Base):
    """
    novels/stories/{story_name}/episodes/{話数}.md

    **一話。** `text` が原稿そのもの。データは `同期` だけを持つ。
    話数はファイル名、題と字数は原稿から採る（書き戻すときも足さない）。
    """

    __tablename__ = "episode"

    story_id: Mapped[str] = mapped_column(String, ForeignKey("story.id"))
    number: Mapped[int | None] = mapped_column(
        Integer, comment="話数。ファイル名の数がそのまま入る。**ゼロ埋めしない**")
    title: Mapped[str] = mapped_column(
        String, default="", comment="サブタイトル。本文の見出しから読む")
    letters: Mapped[int | None] = mapped_column(Integer, comment="字数")
    synced: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="同期フラグ。この話の出来事・行動が台帳へ戻してあるか。"
                "自動生成時はオン、手で書いたときはオフ。"
                "オフの話があるあいだは、次の話の材料を読み出せない")


def create_db(path):
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


def open_db(path):
    """既にある db を開く。"""
    return create_engine(f"sqlite:///{os.path.abspath(path)}", future=True)
