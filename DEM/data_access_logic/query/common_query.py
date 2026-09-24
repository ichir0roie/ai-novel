#!/usr/bin/env python3
"""ストーリー生成(モード 2)のための問い合わせ。`DEM/ai/claude_code/interface/story/` に加え、`DEM/ai/local_ai/`(常駐ループ)からも使う。"""
from __future__ import annotations

import re

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from DEM.db.schema import (
    Character, CharacterPlace, CharacterRelation, Episode,
    Event, EventCharacter, Location,
    Story, Term,
)
from DEM.db.stamp import Stamp, StampError

EVENT_RELATIONS = {"location": "place_name"}

EVENT_LOAD_OPTIONS = (
    selectinload(Event.location),
    selectinload(Event.event_characters).selectinload(EventCharacter.character),
)


class NotFoundError(LookupError):
    """指した id のレコードが db に無い。"""


# ---------------------------------------------------------------- 時刻

def span(when) -> tuple[Stamp, Stamp]:
    """時刻の指定を、**そこに収まる幅**(始め, 終わり)へ開く。

    書いた粒度がそのまま幅になる。`4354` はその年いっぱい、`4354/09/28` は
    その日いっぱい、`4354/09/28 17:00:00` はその一点。
    """
    text = str(when).strip()
    at = Stamp.parse(text)
    if at is None:
        raise StampError("時刻が空")
    depth = 1 if text.isdigit() else len(
        [part for part in re.split(r"[-/ :T]", text) if part])
    parts = [at.year, at.month, at.day, at.hour, at.minute, at.second]
    largest = [None, 12, 31, 23, 59, 59]
    for index in range(min(depth, 6), 6):
        parts[index] = largest[index]
    return at, Stamp(*parts)


def resolve_time(session: Session, when, story: Story | None) -> tuple[Stamp, Stamp]:
    """時刻が省かれたら、作品の立つ年をその幅にする。"""
    if when is not None:
        return span(when)
    if story is not None and story.start is not None:
        return span(story.start.year)
    raise ValueError("時刻が決まらない(作品に立つ年が無いので time を渡す)")


def _get(session: Session, model, id_: int, label: str):
    row = session.get(model, id_)
    if row is None:
        raise NotFoundError(f"{label}={id_} という id の {model.__tablename__} が見つからない")
    return row


def get_story(session: Session, story_id: int) -> Story:
    """作品一件を引く。無ければ `NotFoundError`。"""
    return _get(session, Story, int(story_id), "story_id")


def _in_span(column, since: Stamp, until: Stamp):
    # 列は `StampType` なので、`Stamp` のまま渡す(整数を渡すと年として読まれる)
    return column.between(since, until)


def _alive(model, until: Stamp):
    """その時点で**まだ続いている**行(始まっていて、終わっていない)。"""
    return (or_(model.start.is_(None), model.start <= until),
            or_(model.end.is_(None), model.end > until))


def latest_time_select() -> Select:
    """世界の側で一番新しい出来事の時刻。`time_keepr` のループを再開する起点に使う。"""
    return select(func.max(Event.time))


# ---------------------------------------------------------------- 場所の木

def descendant_place_ids(session: Session, place_id: int) -> list[int]:
    """その場所と、その配下にぶら下がる場所の id を全部返す。何段あるか分からないので一段ずつたどる。"""
    _get(session, Location, place_id, "place_id")
    found = [place_id]
    frontier = [place_id]
    while frontier:
        children = session.scalars(
            select(Location.id).where(Location.parent_id.in_(frontier))).all()
        children = [child for child in children if child not in found]
        found.extend(children)
        frontier = children
    return found


def term_scope_ids(session: Session, place_id: int) -> list[int]:
    """その場所で効く語を引く範囲。配下に加えて、属する星・世界線まで親方向へのぼる。

    `restrict_world_id` / `restrict_planet_id` が指すのは自分より上の場所なので、
    配下だけで引くと世界線に掛かる語が一件も当たらない。
    """
    found = descendant_place_ids(session, place_id)
    seen = set(found)
    current = session.get(Location, place_id)
    while current is not None and current.parent_id:
        current = session.get(Location, current.parent_id)
        if current is None or current.id in seen:
            break
        seen.add(current.id)
        found.append(current.id)
    return found


def place_path(session: Session, place_id: int) -> list[dict]:
    """その場所までの道筋を、上(世界線)から順に返す。"""
    chain: list[dict] = []
    seen: set[int] = set()
    current = session.get(Location, place_id)
    while current is not None and current.id not in seen:
        seen.add(current.id)
        chain.append({"id": current.id, "name": current.name, "kind": current.kind})
        current = session.get(Location, current.parent_id) if current.parent_id else None
    return list(reversed(chain))


def place_up(session: Session, place_id: int, levels: int) -> int:
    """その場所から親を `levels` 段のぼった場所の id(根で止まる)。"""
    current = _get(session, Location, place_id, "place_id")
    for _ in range(max(0, levels)):
        if current.parent_id is None:
            break
        parent = session.get(Location, current.parent_id)
        if parent is None:
            break
        current = parent
    return current.id


# ---------------------------------------------------------------- 場所

def places_select(kind: str | None = None) -> Select:
    """場所の一覧。`kind` を渡すとその種別だけに絞る(例: `"村"`)。"""
    query = select(Location)
    if kind is not None:
        query = query.where(Location.kind == kind)
    return query.order_by(Location.id.asc())


def planets_select() -> Select:
    """星(`kind="星"`)の一覧。"""
    return select(Location).where(Location.kind == "星").order_by(Location.id.asc())


def places_on_planet_select(planet_id: int) -> Select:
    """その星の上で経緯度を持つ場所。距離・方角を出せる行だけ。"""
    return (
        select(Location)
        .where(Location.location_planet == planet_id)
        .where(Location.location_longitude.is_not(None))
        .where(Location.location_latitude.is_not(None))
        .order_by(Location.id.asc())
    )


def shapes_on_planet_select(planet_id: int) -> Select:
    """その星の上で輪郭(polygon)を持つ場所。経緯度の有無は問わない。"""
    return (
        select(Location)
        .where(Location.location_planet == planet_id)
        .where(Location.polygon.is_not(None))
        .order_by(Location.id.asc())
    )


# ---------------------------------------------------------------- 出来事

def events_at_select(when, *, place_ids=None, limit=None) -> Select:
    """**その時(その幅)の出来事と行動。** 場所で絞ってもよい。"""
    since, until = span(when)
    query = (select(Event)
             .options(*EVENT_LOAD_OPTIONS)
             .where(_in_span(Event.time, since, until)))
    if place_ids is not None:
        query = query.where(Event.location_id.in_(list(place_ids)))
    query = query.order_by(Event.time.desc(), Event.id.desc())
    if limit:
        query = query.limit(limit)
    return query


def events_in_locations_select(place_ids, *, until=None, limit=None) -> Select:
    """**複数の場所にまたがる出来事を新しい順に。** `place_ids` が空/None なら場所を問わず全件。

    一つの作品(`Story`)が指す範囲(場所の配下全体、無指定なら世界全体)で
    「直近どんな出来事が使われたか」を見るのに使う。単一の id で引く
    `events_of_select` と違い、場所の集合をそのまま渡す。
    """
    query = select(Event).options(*EVENT_LOAD_OPTIONS)
    if place_ids:
        query = query.where(Event.location_id.in_(list(place_ids)))
    if until is not None:
        query = query.where(Event.time <= span(until)[1])
    query = query.order_by(Event.time.desc(), Event.id.desc())
    if limit:
        query = query.limit(limit)
    return query


def events_of_select(record_id: int, *, until=None, limit=5) -> Select:
    """**その id に掛かる出来事と行動を、新しい順に。**

    場所の id ならそこで起きたこと、人物の id ならその者の行動、
    出来事の id ならそれにぶら下がる行動。
    """
    query = (select(Event)
             .options(*EVENT_LOAD_OPTIONS)
             .where(or_(
                 Event.location_id == record_id,
                 Event.parent_event_id == record_id,
                 Event.event_characters.any(EventCharacter.character_id == record_id),
             )))
    if until is not None:
        query = query.where(Event.time <= span(until)[1])
    query = query.order_by(Event.time.desc(), Event.id.desc())
    if limit:
        query = query.limit(limit)
    return query


def events_select() -> Select:
    """**db にある出来事を全件、新しい順に。**"""
    return (select(Event)
            .options(*EVENT_LOAD_OPTIONS)
            .order_by(Event.time.desc(), Event.id.desc()))


def open_events_select(place_ids, until: Stamp) -> Select:
    """**まだ終わっていない出来事**(`end` が空か、その先)。張っているもの。

    誰の行動でもない「ただ起きたこと」だけを拾う(人物に掛かっていないもの)。
    """
    return (select(Event)
            .options(*EVENT_LOAD_OPTIONS)
            .where(Event.location_id.in_(list(place_ids)),
                   Event.time <= until,
                   or_(Event.end.is_(None), Event.end > until),
                   ~Event.event_characters.any())
            .order_by(Event.time.desc(), Event.id.desc()))


# ---------------------------------------------------------------- 人物

def character_place_select(character_id: int, until: Stamp) -> Select:
    """その時点の居場所(`character_place` の生きている行、新しい順)。"""
    return (select(CharacterPlace)
            .options(selectinload(CharacterPlace.place))
            .where(CharacterPlace.character_id == character_id, *_alive(CharacterPlace, until))
            .order_by(CharacterPlace.start.desc(), CharacterPlace.id.desc()))


def latest_character_event_select(character_id: int) -> Select:
    """**その人物が当事者の出来事のうち、終わりが一番新しい一件。** `end` が空ならその始まりで比べる。"""
    finished = func.coalesce(Event.end, Event.start, Event.time)
    return (select(Event)
            .options(*EVENT_LOAD_OPTIONS)
            .where(Event.event_characters.any(EventCharacter.character_id == character_id))
            .order_by(finished.desc(), Event.id.desc())
            .limit(1))


def latest_character_place_select(character_id: int) -> Select:
    """その人物の居場所のうち、一番新しく始まった行(時刻は問わない)。"""
    return (select(CharacterPlace)
            .where(CharacterPlace.character_id == character_id)
            .order_by(CharacterPlace.start.desc(), CharacterPlace.id.desc())
            .limit(1))


def resident_character_ids_select(place_ids, until: Stamp) -> Select:
    """その時点でその場所(群)に居る人物の id。"""
    return (select(CharacterPlace.character_id).distinct()
            .where(CharacterPlace.location_id.in_(list(place_ids)), *_alive(CharacterPlace, until)))


def character_select(character_id: int) -> Select:
    """人物一件。"""
    return select(Character).where(Character.id == character_id)


def characters_select() -> Select:
    """人物の一覧。既存キャラクターを一括で見渡すのに使う。"""
    return (select(Character)
            .options(selectinload(Character.places))
            .order_by(Character.id.asc()))


# ---------------------------------------------------------------- 作品

def story_select(story_id: int) -> Select:
    """作品一件。世界線・立つ場所の関連を積んでおく。"""
    return (select(Story)
            .options(selectinload(Story.world), selectinload(Story.place))
            .where(Story.id == story_id))


def stories_select() -> Select:
    """作品の一覧。世界線・立つ場所の関連を積んでおく。"""
    return (select(Story)
            .options(selectinload(Story.world), selectinload(Story.place))
            .order_by(Story.id))


def story_episodes_select(story_id: int) -> Select:
    """その作品の話を、話数の若い順に全部(`story_digest` が数えるのに使う)。"""
    return (select(Episode)
            .where(Episode.story_id == story_id)
            .order_by(Episode.number))


def episodes_select(story_id: int, *, count: int = 10, before=None) -> Select:
    """**直前の `count` 話を、話数の新しい順に返す select。**

    呼び出し側は取り出した後に `reversed()` して古い順に並べ直す
    (新しい順に `limit` するため、select 自体は新しい順のまま返す)。
    `before` を渡すと、その話数より前の `count` 話。
    """
    query = select(Episode).where(Episode.story_id == story_id)
    if before is not None:
        query = query.where(Episode.number < int(before))
    return query.order_by(Episode.number.desc()).limit(count)


def unsynced_episodes_select(story_id: int | None = None) -> Select:
    """**同期フラグの下りている話。** 作品名を引けるよう `story` を積む。"""
    query = (select(Episode)
             .options(selectinload(Episode.story))
             .where(Episode.synced.is_(False)))
    if story_id is not None:
        query = query.where(Episode.story_id == story_id)
    return query.order_by(Episode.story_id, Episode.number)


# ---------------------------------------------------------------- 断面

def terms_select(place_ids) -> Select:
    """その場所(群)で使われる語。"""
    place_ids = list(place_ids)
    return (select(Term)
            .where(or_(Term.restrict_place_id.in_(place_ids),
                       Term.restrict_planet_id.in_(place_ids),
                       Term.restrict_world_id.in_(place_ids)))
            .order_by(Term.id))


def character_relations_select(character_id: int | None = None) -> Select:
    """人物の相関(`CharacterRelation`)の一覧。人物を渡すと、その人物が主体か相手のものに絞る。"""
    query = select(CharacterRelation)
    if character_id is not None:
        query = query.where(or_(CharacterRelation.character_id_1 == character_id,
                                CharacterRelation.character_id_2 == character_id))
    return query.order_by(CharacterRelation.id)
