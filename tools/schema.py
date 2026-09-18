#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime

import os

from sqlalchemy import (
    Float, Integer, String, TIME, DECIMAL,
    create_engine, ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    src: Mapped[str] = mapped_column(String, default="", nullable=False)

    text: Mapped[str] = mapped_column(String, default="", nullable=False)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="主キー,md内に記載される。")


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

    start: Mapped[datetime | None] = mapped_column(TIME)
    end: Mapped[datetime | None] = mapped_column(TIME)


class Event(Base):
    """
    novels/worlds/{place_name}/**/events/{yyyymmddhhmmss}_{event_name}.md
    """

    __tablename__ = "event"

    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="")
    time: Mapped[datetime] = mapped_column(TIME)

    parent_event_id: Mapped[str | None] = mapped_column(String, ForeignKey("event.id"))

    place_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))
    place: Mapped[Place | None] = relationship(lazy="noload")

    start: Mapped[datetime | None] = mapped_column(TIME)
    end: Mapped[datetime | None] = mapped_column(TIME)

    child_events: Mapped[list["Event"]] = relationship(
        backref="parent_event", lazy="selectin", cascade="all, delete-orphan"
    )


class Character(Base):
    """
    novels/characters/{root_place_name}/{character_name}.md
    """

    __tablename__ = "character"

    name: Mapped[str] = mapped_column(String)
    read: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)

    root_place_id: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))

    start: Mapped[datetime | None] = mapped_column(TIME)
    end: Mapped[datetime | None] = mapped_column(TIME)


class Actor(Base):
    """
    novels/actors/{root_place_name}/**/{actor_name}/actor.md
    """
    __tablename__ = "actor"

    root_place_name: Mapped[str | None] = mapped_column(String, ForeignKey("place.id"))

    name: Mapped[str] = mapped_column(String)
    read: Mapped[str] = mapped_column(String)

    character_id: Mapped[str] = mapped_column(String, ForeignKey("character.id"))
    kind: Mapped[str] = mapped_column(String)

    start: Mapped[datetime | None] = mapped_column(TIME)
    end: Mapped[datetime | None] = mapped_column(TIME)


class ActorPlace(Base):
    """
    {actor_name}/places/{yyyymmddhhmmss}_{place_name}.md
    """

    __tablename__ = "actor_place"

    actor_id: Mapped[str] = mapped_column(String, ForeignKey("actor.id"))
    place_id: Mapped[str] = mapped_column(String, ForeignKey("place.id"))

    start: Mapped[datetime | None] = mapped_column(TIME)
    end: Mapped[datetime | None] = mapped_column(TIME)


class Action(Base):
    """
    {actor_name}/actions/{yyyymmddhhmmss}_{action_name}.md
    """
    __tablename__ = "actor_event"

    actor_id: Mapped[str] = mapped_column(String, ForeignKey("actor.id"))
    event_id: Mapped[str] = mapped_column(String, ForeignKey("event.id"))

    start: Mapped[datetime | None] = mapped_column(TIME)
    end: Mapped[datetime | None] = mapped_column(TIME)


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
