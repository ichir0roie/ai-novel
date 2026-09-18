#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime

import os

from sqlalchemy import (
    DateTime, Integer, String, DECIMAL,
    create_engine, ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    src: Mapped[str] = mapped_column(String, default="", nullable=False, comment="出典。どの md から来たか")

    text: Mapped[str] = mapped_column(String, default="", nullable=False, comment="front matter の下の本文")

    id: Mapped[str] = mapped_column(String, primary_key=True, comment="主キー,md内に記載される。")


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

    start: Mapped[datetime | None] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)


class Event(Base):
    """
    novels/worlds/{place_name}/**/events/{yyyymmddhhmmss}_{event_name}.md
    """

    __tablename__ = "event"

    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="")
    time: Mapped[datetime] = mapped_column(DateTime)

    parent_event_id: Mapped[str | None] = mapped_column(String, ForeignKey("event.id"))

    place_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))
    place: Mapped[Place | None] = relationship(lazy="noload")

    start: Mapped[datetime | None] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)

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

    start: Mapped[datetime | None] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)


class Object(Base):
    """
    novels/actors/{root_place_name}/**/{actor_name}/actor.md

    舞台装置として、個、または多数の存在として行動する。
    """
    __tablename__ = "object"

    root_place_name: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))

    name: Mapped[str] = mapped_column(String)
    read: Mapped[str] = mapped_column(String)

    kind_id: Mapped[str] = mapped_column(String, ForeignKey("kind.id"))
    kind: Mapped[str] = mapped_column(String)

    start: Mapped[datetime | None] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)


class ObjectPlace(Base):
    """
    {object_name}/places/{yyyymmddhhmmss}_{place_name}.md
    """

    __tablename__ = "object_place"

    object_id: Mapped[str] = mapped_column(String, ForeignKey("object.id"))
    place_id: Mapped[str] = mapped_column(String, ForeignKey("place.id"))

    start: Mapped[datetime | None] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)


class ObjectAction(Base):
    """
    {object_name}/actions/{yyyymmddhhmmss}_{action_name}.md
    """
    __tablename__ = "object_event"

    object_id: Mapped[str] = mapped_column(String, ForeignKey("object.id"))
    event_id: Mapped[str] = mapped_column(String, ForeignKey("event.id"))

    start: Mapped[datetime | None] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)


class Character(Base):
    """
    novels/characters/{born_place_name}/**/{character_name}/character.md

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

    start: Mapped[datetime | None] = mapped_column(DateTime, comment="生")
    end: Mapped[datetime | None] = mapped_column(DateTime, comment="没")


class CharacterPlace(Base):
    """
    {character_name}/places/{yyyymmddhhmmss}_{place_name}.md
    """

    __tablename__ = "character_place"

    character_id: Mapped[str] = mapped_column(String, ForeignKey("character.id"))
    place_id: Mapped[str] = mapped_column(String, ForeignKey("place.id"))

    start: Mapped[datetime | None] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)


class CharacterAction(Base):
    """
    {character_name}/actions/{yyyymmddhhmmss}_{action_name}.md
    """
    __tablename__ = "character_event"

    character_id: Mapped[str] = mapped_column(String, ForeignKey("character.id"))
    event_id: Mapped[str] = mapped_column(String, ForeignKey("event.id"))

    start: Mapped[datetime | None] = mapped_column(DateTime)
    end: Mapped[datetime | None] = mapped_column(DateTime)


class Term(Base):
    """
    novels/terms/{term_name}.md
    """
    __tablename__ = "term"

    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)

    restrict_world_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))
    restrict_planet_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))
    restrict_place_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))


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
