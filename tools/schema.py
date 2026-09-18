#!/usr/bin/env python3
from __future__ import annotations

import os

from sqlalchemy import (
    BigInteger, Integer, String, DECIMAL, TypeDecorator,
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

    location_world: Mapped[float | None] = mapped_column(DECIMAL)
    location_planet: Mapped[int | None] = mapped_column(Integer)
    location_longitude: Mapped[float | None] = mapped_column(DECIMAL, comment="経度")
    location_latitude: Mapped[float | None] = mapped_column(DECIMAL, comment="緯度")
    location_altitude: Mapped[float | None] = mapped_column(DECIMAL, comment="高度")

    # 宇宙の座標系における位置を表すためのフィールド群
    location_x: Mapped[float | None] = mapped_column(DECIMAL, comment="宇宙座標系 X")
    location_y: Mapped[float | None] = mapped_column(DECIMAL, comment="宇宙座標系 Y")
    location_z: Mapped[float | None] = mapped_column(DECIMAL, comment="宇宙座標系 Z")

    start: Mapped[Stamp | None] = mapped_column(StampType)
    end: Mapped[Stamp | None] = mapped_column(StampType)


class Event(Base):
    """
    novels/worlds/{place_name}/**/events/{yyyymmddhhmmss}_{event_name}.md
    """

    __tablename__ = "event"

    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="")
    time: Mapped[Stamp] = mapped_column(StampType)

    parent_event_id: Mapped[str | None] = mapped_column(String, ForeignKey("event.id"))

    place_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))
    place: Mapped[Place | None] = relationship(lazy="noload")

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


class ObjectAction(Base):
    """
    {object_name}/actions/{yyyymmddhhmmss}_{action_name}.md
    """
    __tablename__ = "object_event"

    object_id: Mapped[str] = mapped_column(String, ForeignKey("object.id"))
    event_id: Mapped[str] = mapped_column(String, ForeignKey("event.id"))

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


class CharacterAction(Base):
    """
    {character_name}/actions/{yyyymmddhhmmss}_{action_name}.md
    """
    __tablename__ = "character_event"

    character_id: Mapped[str] = mapped_column(String, ForeignKey("character.id"))
    event_id: Mapped[str] = mapped_column(String, ForeignKey("event.id"))

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
    novels/stories/{story_name}/episodes/{nnn}.md

    **一話。** `text` が原稿そのもの。上段の欄は持たない
    （本文のファイルに上段を足さない。書き戻すときも原稿だけを書く）。
    """

    __tablename__ = "episode"

    story_id: Mapped[str] = mapped_column(String, ForeignKey("story.id"))
    number: Mapped[int | None] = mapped_column(Integer, comment="話数")
    title: Mapped[str] = mapped_column(
        String, default="", comment="サブタイトル。本文の見出しから読む")
    letters: Mapped[int | None] = mapped_column(Integer, comment="字数")



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
