#!/usr/bin/env python3
"""世界観構成で確定する前に確かめる、数の整合。`DEM/ai/claude_code/interface/randomizer/` と `DEM/ai/local_ai/` から使う。"""
from __future__ import annotations

from sqlalchemy import Select, and_, func, or_, select

from DEM.data_access_logic.query import common_query
from DEM.db.schema import (
    Character, Event, EventCharacter, Location, Session, Stamp, Story,
)


def siblings_area_sum_select(parent_id: int) -> Select:
    """同じ親(`parent_id`)を持つ場所の、広さ(`area`)の合計。"""
    return (select(func.coalesce(func.sum(Location.area), 0))
            .where(Location.parent_id == parent_id))


def busy_character_ids_select(time) -> Select:
    """時刻 `time` に、進行中の出来事(`start`〜`end` がその時を含む)へ関わっている人物の id。"""
    return (
        select(EventCharacter.character_id).distinct()
        .join(Event, Event.id == EventCharacter.event_id)
        .where(
            Event.start.is_not(None),
            Event.start <= time,
            or_(Event.end.is_(None), Event.end > time))
    )


def alive_locations_select(time) -> Select:
    """時刻 `time` にまだ存在している場所だけ(`start` 以後・`end` より前。無指定側は素通し)。"""
    return (
        select(Location)
        .where(
            or_(Location.start.is_(None), Location.start <= time),
            or_(Location.end.is_(None), Location.end > time))
    )


def alive_characters_select(time) -> Select:
    """時刻 `time` にまだ生きている人物だけ(`start` 以後・`end` より前。居場所は見ない)。"""
    return (select(Character)
            .where(or_(Character.start.is_(None), Character.start <= time),
                   or_(Character.end.is_(None), Character.end > time)))


def active_story_count_select(time) -> Select:
    """時刻 `time` をカバーしている作品(`Story`)の件数(`place_id` は問わない)。"""
    return (select(func.count(Story.id))
            .where(or_(Story.start.is_(None), Story.start <= time),
                   or_(Story.end.is_(None), Story.end > time)))


def check_within_parent_span(parent: Location, child_start, child_end, label: str) -> None:
    """子(人物・場所)の `start`〜`end` が、親の場所の `start`〜`end` に収まっているか確かめる。"""
    # 入口からは JSON 由来の文字列で来るので、比較の前に Stamp にそろえる。
    child_start = Stamp.parse(child_start)
    child_end = Stamp.parse(child_end)
    if parent.start is not None:
        if child_start is not None and child_start < parent.start:
            raise ValueError(
                f"{label}: start={child_start} が親(id={parent.id})の "
                f"start={parent.start} より前")
    if parent.end is not None:
        if child_start is not None and child_start >= parent.end:
            raise ValueError(
                f"{label}: start={child_start} が親(id={parent.id})の "
                f"end={parent.end} 以後")
        if child_end is not None and child_end > parent.end:
            raise ValueError(
                f"{label}: end={child_end} が親(id={parent.id})の "
                f"end={parent.end} を超える")


def location_has_story(session: Session, place_id: int) -> bool:
    """その場所(か祖先)に `Story` が一件でもあるか。時期は問わない。"""
    ancestor_ids = [node["id"] for node in common_query.place_path(session, place_id)]
    return session.scalar(
        select(Story.id)
        .where(Story.place_id.in_(ancestor_ids))
        .limit(1)
    ) is not None


def check_has_story(session: Session, place_id: int, label: str) -> None:
    """その場所(か祖先)に作品(`Story`)が一件も無ければ止める。"""
    if not location_has_story(session, place_id):
        raise ValueError(
            f"{label}: place_id={place_id} には作品が無い。"
            "先に CommitStory でその場所(か祖先)へ作品を置いてから確定する")
