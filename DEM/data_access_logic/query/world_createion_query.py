#!/usr/bin/env python3
"""**世界観構成(モード 1)で確定する前に確かめる、数の整合。** 下地の実装。

claude はここを直接呼ばない。`DEM/claude_interface/randomizer/` の
「確定する」入口(`CommitPlace` `CommitCharacter` 等)と、`DEM/local_ai/`
の常駐生成処理の両方から使う。

`common_query.py` と同じく、関数はほとんど `Select` を返すだけにとどめる
(実行と、実行結果をもとにした判定は呼び出し側へ渡す)。例外は
`check_within_parent_span` だけ: 親と子、二つのレコードを見比べる算術で、
select で表せる問いではない(`common_query.py` の `descendant_place_ids` 等と
同じ理由)。
"""
from __future__ import annotations

from sqlalchemy import Select, func, or_, select

from DEM.db.schema import Character, Location, LocationResource, Object

# 一つの場所につき作れる人物・個体は、それぞれ最大でこの件数まで。
MAX_PER_LOCATION = 10


def character_count_at_place_select(place_id: int) -> Select:
    """その場所(`born_place_id`)を出自に持つ人物の数。"""
    return select(func.count(Character.id)).where(Character.born_place_id == place_id)


def object_count_at_place_select(place_id: int) -> Select:
    """その場所(`root_place_name`)を出自に持つ個体(群)の数。"""
    return select(func.count(Object.id)).where(Object.root_place_name == place_id)


def siblings_area_sum_select(parent_id: int) -> Select:
    """同じ親(`parent_id`)を持つ場所の、広さ(`area`)の合計。"""
    return (select(func.coalesce(func.sum(Location.area), 0))
            .where(Location.parent_id == parent_id))


def alive_locations_select(time) -> Select:
    """**時刻 `time` にまだ存在している場所だけ。**(`start` 以後・`end` より前)

    `start` `end` が無い場所は、その側の縛りが無いものとして通す。
    新しく生む人物・個体・場所の親を探すときは、まだ無い場所や、既に
    終わった場所を親にしないよう、必ずここを通す。
    """
    return (select(Location)
            .where(or_(Location.start.is_(None), Location.start <= time))
            .where(or_(Location.end.is_(None), Location.end > time)))


def locations_without_current_resource_select(time) -> Select:
    """**時刻 `time` に、有効な資源(`start`〜`end` が `time` を含む)を
    一つも持っていない、生きている場所。**

    場所が生まれた直後(まだ資源が無い)と、前の資源が尽きた後
    (`end` を過ぎた)の両方を拾う。次の資源を足す場所を選ぶのに使う。
    """
    covered = (select(LocationResource.location_id)
               .where(LocationResource.start <= time)
               .where(LocationResource.end > time))
    return alive_locations_select(time).where(Location.id.not_in(covered))


def alive_characters_select(time) -> Select:
    """**時刻 `time` にまだ生きている人物だけ。**(`start` 以後・`end` より前)

    `alive_locations_select` と同じ理由・同じ形。人物の一生(`start`〜`end`)
    を見るのであって、居場所(`character_place`)は見ない。
    """
    return (select(Character)
            .where(or_(Character.start.is_(None), Character.start <= time))
            .where(or_(Character.end.is_(None), Character.end > time)))


def alive_objects_select(time) -> Select:
    """**時刻 `time` にまだ存在している個体(群)だけ。**(`start` 以後・`end` より前)

    `alive_locations_select` と同じ理由・同じ形。
    """
    return (select(Object)
            .where(or_(Object.start.is_(None), Object.start <= time))
            .where(or_(Object.end.is_(None), Object.end > time)))


def check_within_parent_span(parent: Location, child_start, child_end, label: str) -> None:
    """子(人物・個体・場所)の `start`〜`end` が、親の場所の `start`〜`end` に収まっているか確かめる。

    親の側が空(縛りが無い)ならそちら側は素通しする。
    """
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
