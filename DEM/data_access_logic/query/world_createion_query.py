#!/usr/bin/env python3
"""**世界観構成(モード 1)で確定する前に確かめる、数の整合。** 下地の実装。

claude はここを直接呼ばない。`DEM/claude_interface/randomizer/` の
「確定する」入口(`CommitPlace` `CommitCharacter` 等)と、`DEM/local_ai/`
の常駐生成処理の両方から使う。

`common_query.py` と同じく、関数はほとんど `Select` を返すだけにとどめる
(実行と、実行結果をもとにした判定は呼び出し側へ渡す)。例外は
`check_within_parent_span` `check_has_plot` だけ: 親と子、二つのレコードを
見比べる算術や、場所の木をのぼる処理で、select 一発では表せない問い
(`common_query.py` の `descendant_place_ids` 等と同じ理由)。
"""
from __future__ import annotations

from sqlalchemy import Select, func, or_, select

from DEM.data_access_logic.query import common_query
from DEM.db.schema import (
    Character, Event, EventCharacter, Location, LocationResource, Object,
    Plot, Session,
)

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


def flagged_character_source_locations_select(time) -> Select:
    """**`random_character_source` がオンで、時刻 `time` に生きている場所。**

    まとめて人物を生む対象の候補。まだ誰も人物が居ないかどうかは、返った
    場所それぞれに `character_count_at_place_select` を当てて呼び出し側が
    確かめる(`random_character_generator.seed_initial_characters`)。
    """
    return alive_locations_select(time).where(
        Location.random_character_source.is_(True))


def busy_character_ids_select(time) -> Select:
    """**時刻 `time` に、進行中の出来事(`start`〜`end` がその時を含む)へ
    関わっている人物の id。**

    進行中の出来事がある人物は、次の出来事の対象から外す
    (`event_progression_generator._group_by_place`)。`start` を持たない
    出来事(この仕組みを入れる前の、旧来の出来事)は対象にしない。
    """
    return (
        select(EventCharacter.character_id).distinct()
        .join(Event, Event.id == EventCharacter.event_id)
        .where(Event.start.is_not(None))
        .where(Event.start <= time)
        .where(or_(Event.end.is_(None), Event.end > time))
    )


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


def active_resources_select(location_id: int, time) -> Select:
    """**時刻 `time` に、その場所(`location_id`)でまだ有効な資源(`start`〜`end` が `time` を含む)。**

    出来事の結果としてその場所の資源が尽きた(枯渇・破壊された)ときに、
    `end` を今の時刻へ繰り上げる対象を拾うのに使う。
    """
    return (select(LocationResource)
            .where(LocationResource.location_id == location_id)
            .where(LocationResource.start <= time)
            .where(LocationResource.end > time))


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


def location_has_plot(session: Session, place_id: int) -> bool:
    """**その場所(か祖先、か場所を問わない筋書き)に `Plot` が一件でもあるか。**

    `Plot.location_id` が無い(場所を問わず渡る)行が一件でもあれば、どの
    場所でも真になる。場所を限った行は、その場所自身か、木をのぼった祖先
    (`common_query.place_path`)のどれかに掛かっていれば真になる。時期
    (`start`〜`end`)は問わない——存在するかどうかだけを見る。

    `check_has_plot`(「確定する」入口が止まるときに使う)と、
    `DEM/local_ai/time_keeper/` の自動生成が候補地を絞るときの両方から使う
    (`IHG` の基準は Claude を介さないローカル AI にも同じく守らせる)。
    """
    ancestor_ids = [node["id"] for node in common_query.place_path(session, place_id)]
    return session.scalar(
        select(Plot.id)
        .where(or_(Plot.location_id.in_(ancestor_ids), Plot.location_id.is_(None)))
        .limit(1)
    ) is not None


def check_has_plot(session: Session, place_id: int, label: str) -> None:
    """**その場所(か祖先)に筋書き(`Plot`)が一件も無ければ止める。**

    プロットの無いエリアに人物・個体を増やさない——展開の当てが無いまま
    人・物だけが積み上がるのを防ぐ。
    """
    if not location_has_plot(session, place_id):
        raise ValueError(
            f"{label}: place_id={place_id} にはプロットが無い。"
            "先に CommitPlot でその場所(か祖先)へ筋書きを置いてから確定する")
