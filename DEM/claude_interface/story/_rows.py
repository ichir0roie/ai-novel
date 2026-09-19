#!/usr/bin/env python3
"""**`query.py` の Select を実行して、辞書に組む共通処理。**

先頭が `_` なので、それ自体は claude が呼ぶ入口ではない（`readme.md` の
「一つの呼び出し機能だけ」に沿って、この下の各 `read_*.py` / `list_*.py` /
`start_story.py` が薄く被せる）。ただ、複数の入口が同じ組み立て
（人物一件・断面・顔ぶれ…）を要るので、ここに一度だけ書く。

ORM → dict の変換は `DEM.db.schema_pydantic.to_dict_with` を使う。
relationship はあらかじめ `query.py` 側の select が `selectinload` で
積んであるので、ここでは追加クエリを打たず、ロード済みの関連から
名前を読むだけにする。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from DEM.data_access_logic.query import common_query
from DEM.db.schema import Character, Event, Location, Object, Story
from DEM.db.schema_pydantic import to_dict_with
from DEM.db.stamp import Stamp


def event_row(event, *, text: bool = True) -> dict:
    """出来事一件を辞書にする。掛かる人物・個体は**何人・何個体でも**並ぶ。"""
    data = to_dict_with(event, relations=common_query.EVENT_RELATIONS, text=text)
    data["characters"] = [
        {"id": link.character_id, "name": None if link.character is None else link.character.name}
        for link in event.event_characters]
    data["objects"] = [
        {"id": link.object_id, "name": None if link.object is None else link.object.name}
        for link in event.event_objects]
    return data


def events_at(session: Session, when, *, place_ids=None, limit=None,
              text: bool = True) -> list[dict]:
    rows = session.scalars(
        common_query.events_at_select(when, place_ids=place_ids, limit=limit)).all()
    return [event_row(row, text=text) for row in rows]


def events_of(session: Session, record_id: int, *, until=None, limit=5,
              text: bool = True) -> list[dict]:
    rows = session.scalars(
        common_query.events_of_select(record_id, until=until, limit=limit)).all()
    return [event_row(row, text=text) for row in rows]


def open_events(session: Session, place_ids, until: Stamp) -> list[dict]:
    rows = session.scalars(common_query.open_events_select(place_ids, until)).all()
    return [event_row(row) for row in rows]


def residents(session: Session, place_ids, until: Stamp) -> tuple[list[int], list[int]]:
    """その時点でその場所（群）に居る人物と個体の id。"""
    character_ids = session.scalars(
        common_query.resident_character_ids_select(place_ids, until)).all()
    object_ids = session.scalars(
        common_query.resident_object_ids_select(place_ids, until)).all()
    return ([id_ for id_ in character_ids if id_ is not None],
            [id_ for id_ in object_ids if id_ is not None])


def _place_at(session: Session, select_fn, owner_id: int, until: Stamp) -> dict | None:
    row = session.scalars(select_fn(owner_id, until)).first()
    if row is None:
        return None
    return {"place_id": row.location_id,
            "place_name": None if row.place is None else row.place.name,
            "start": None if row.start is None else str(row.start)}


def character_sheet(session: Session, character_id: int, *, until=None,
                    count: int = 5, text: bool = True) -> dict:
    """人物一件を、**本文を書くのに要るものだけ**そろえて返す。

    口調（一人称・二人称・三人称）・性格の値・技・生きている情動・
    その時点の居場所・直近の行動。
    """
    character = session.scalars(common_query.character_select(character_id)).first()
    if character is None:
        raise common_query.NotFoundError(f"character_id={character_id} という id の character が見つからない")
    at = common_query.span(until)[1] if until is not None else Stamp(99999, 12, 31, 23, 59, 59)

    sheet = to_dict_with(character, relations={
        "kind": "kind_name", "belong": "belong_name", "born_place": "born_place_name"},
        text=text)
    sheet["place"] = _place_at(session, common_query.character_place_select, character_id, at)
    sheet["emotions"] = [to_dict_with(row) for row in
                         session.scalars(common_query.emotions_select(character_id, at)).all()]
    sheet["skills"] = [
        {"skill_id": held.skill.id, "name": held.skill.name, "level": held.level,
         "cost": held.skill.cost, "effect": held.skill.effect, "range": held.skill.range,
         "duration": held.skill.duration, "target": held.skill.target,
         "constraint": held.skill.constraint}
        for held in session.scalars(common_query.skills_select(character_id)).all()]
    sheet["recent_events"] = events_of(
        session, character_id, until=None if until is None else at,
        limit=count, text=text)
    return sheet


def object_sheet(session: Session, object_id: int, *, until=None,
                 count: int = 5, text: bool = True) -> dict:
    """個体（群）一件。人物と同じ形でそろえる。"""
    obj = session.scalars(common_query.object_select(object_id)).first()
    if obj is None:
        raise common_query.NotFoundError(f"object_id={object_id} という id の object が見つからない")
    at = common_query.span(until)[1] if until is not None else Stamp(99999, 12, 31, 23, 59, 59)

    sheet = to_dict_with(obj, relations={"kind": "kind_name"}, text=text)
    sheet["place"] = _place_at(session, common_query.object_place_select, object_id, at)
    sheet["recent_events"] = events_of(session, object_id, until=at, limit=count, text=text)
    return sheet


def story_digest(session: Session, story: Story) -> dict:
    """作品一件の見出し。話数・未同期の数まで含める。"""
    episodes = session.scalars(common_query.story_episodes_select(story.id)).all()
    digest = to_dict_with(
        story, relations={"world": "world_name", "place": "place_name"})
    digest["episode_count"] = len(episodes)
    digest["last_episode"] = episodes[-1].number if episodes else None
    digest["unsynced"] = [episode.number for episode in episodes if not episode.synced]
    return digest


def stories(session: Session) -> list[dict]:
    rows = session.scalars(common_query.stories_select()).all()
    return [story_digest(session, story) for story in rows]


def episodes(session: Session, story_id: int, *, count: int = 10, before=None,
             text: bool = True) -> list[dict]:
    """**直前の `count` 話を、古い順に並べて返す。**

    `before` を渡すと、その話数より前の `count` 話。`text=False` なら
    話数と題だけ（一覧を見るとき）。
    """
    common_query._get(session, Story, story_id, "story_id")
    rows = session.scalars(
        common_query.episodes_select(story_id, count=count, before=before)).all()
    return [to_dict_with(episode, text=text) for episode in reversed(rows)]


def unsynced_episodes(session: Session, story_id: int | None = None) -> list[dict]:
    """**同期フラグの下りている話。** 一件でも残っていればモード 3 が先。"""
    rows = session.scalars(common_query.unsynced_episodes_select(story_id)).all()
    return [{"id": episode.id, "story_id": episode.story_id,
             "story_name": None if episode.story is None else episode.story.name,
             "number": episode.number, "title": episode.title}
            for episode in rows]


def brief(session: Session, place_id: int, when=None, *, reach: int = 60,
          full: bool = False) -> dict:
    """**世界がいまどうなっているか**（断面）を一枚にまとめる。

    その場所の道筋、配下で張っている出来事、`reach` 年ぶんの直近の出来事、
    そこで使われる語、いま居る者の名前。

    `full=False`（既定）では裏の種別（`裏` `伏線`）を伏せる。
    住人が知らないことを本文に書かないため。
    """
    location = common_query._get(session, Location, place_id, "place_id")
    if when is None:
        raise ValueError("時刻が決まらない（when を渡す）")
    since, until = common_query.span(when)
    place_ids = common_query.descendant_place_ids(session, place_id)

    def visible(rows):
        if full:
            return rows
        return [row for row in rows if row.get("kind") not in common_query.HIDDEN_EVENT_KINDS]

    recent_query = (select(Event)
                    .options(*common_query.EVENT_LOAD_OPTIONS)
                    .where(Event.place_id.in_(place_ids))
                    .where(Event.time <= until)
                    .where(Event.time >= Stamp(max(1, since.year - reach)))
                    .order_by(Event.time.desc(), Event.id.desc()))
    recent = [event_row(row) for row in session.scalars(recent_query).all()]

    character_ids, object_ids = residents(session, place_ids, until)
    terms = session.scalars(common_query.terms_select(place_ids)).all()

    character_names = _names_for(session, character_ids, "Character")
    object_names = _names_for(session, object_ids, "Object")

    return {
        "place": to_dict_with(location),
        "path": common_query.place_path(session, place_id),
        "time": str(until),
        "reach": reach,
        "open_events": visible(open_events(session, place_ids, until)),
        "recent_events": visible(recent),
        "terms": [{"id": term.id, "name": term.name, "kind": term.kind,
                   "text": term.text} for term in terms],
        "present_characters": [
            {"id": id_, "name": character_names.get(id_)} for id_ in character_ids],
        "present_objects": [
            {"id": id_, "name": object_names.get(id_)} for id_ in object_ids],
    }


_NAME_MODELS = {"Character": Character, "Object": Object, "Location": Location}


def _names_for(session: Session, ids: list[int], model_name: str) -> dict[int, str | None]:
    """複数の id の名前を、追加の select 一発でまとめて引く。"""
    if not ids:
        return {}
    model = _NAME_MODELS[model_name]
    rows = session.scalars(select(model).where(model.id.in_(ids))).all()
    return {row.id: row.name for row in rows}


def cast(session: Session, story_id: int, when=None, *, count: int = 5,
         levels: int = 1) -> dict:
    """**その話に出せる顔ぶれ。**

    作品の立つ場所から `levels` 段のぼったところを基準に、その配下に
    その時点で居る人物と個体を集め、一人（一群）ずつ直近 `count` 件の
    出来事を添える。隣の集落にいる者も枠に入れるため、既定で一段のぼる。
    """
    story = common_query._get(session, Story, story_id, "story_id")
    if story.place_id is None:
        raise ValueError(f"作品 {story.name} に立つ場所（place_id）が無い")
    _, until = common_query.resolve_time(session, when, story)
    root_id = common_query.place_up(session, story.place_id, levels)
    place_ids = common_query.descendant_place_ids(session, root_id)
    character_ids, object_ids = residents(session, place_ids, until)
    return {
        "story": {"id": story.id, "name": story.name},
        "time": str(until),
        "scope": {"id": root_id, "name": _names_for(session, [root_id], "Location").get(root_id),
                  "path": common_query.place_path(session, root_id)},
        "characters": [
            character_sheet(session, id_, until=until, count=count, text=False)
            for id_ in character_ids],
        "objects": [
            object_sheet(session, id_, until=until, count=count, text=False)
            for id_ in object_ids],
    }
