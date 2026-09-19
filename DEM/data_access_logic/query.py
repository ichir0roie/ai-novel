#!/usr/bin/env python3
"""**ストーリー生成（モード 2）のための問い合わせ。** 下地の実装。

claude はここを直接呼ばない。`DEM/claude_interface/story/` の入口越しに使う。

引く条件は**時刻とレコードの id だけ**で表す（`IHG/workflow.md`）。
呼ぶ側が SQL を組み立てなくて済むように、モード 2 で要る引き方を
ここに関数として並べる。戻り値は**素の辞書だけ**——
プロセスをまたいでも中身が運べるように、ORM のオブジェクトも session も返さない。
"""
from __future__ import annotations

import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from DEM.db.schema import (
    Character, CharacterEmotion, CharacterPlace, CharacterSkill, Episode,
    Event, Kind, Location, Object, ObjectPlace, Skill, Story, Term,
)
from DEM.db.schema_pydantic import to_dict
from DEM.db.stamp import Stamp, StampError

# 出来事が「誰の・どこの・どれに掛かる」を持つ欄
EVENT_REFS = ("place_id", "character_id", "object_id", "parent_event_id")

# 断面に出さない出来事の種別（裏の設計。住人が知らないこと）
HIDDEN_EVENT_KINDS = ("裏", "伏線")


class NotFoundError(LookupError):
    """指した id のレコードが db に無い。"""


# ---------------------------------------------------------------- 時刻

def span(when) -> tuple[Stamp, Stamp]:
    """時刻の指定を、**そこに収まる幅**（始め, 終わり）へ開く。

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
    raise ValueError("時刻が決まらない（作品に立つ年が無いので time を渡す）")


def get_story(session: Session, story_id: int) -> Story:
    """作品一件を引く。無ければ `NotFoundError`。"""
    return _get(session, Story, int(story_id), "story_id")


def _in_span(column, since: Stamp, until: Stamp):
    # 列は `StampType` なので、`Stamp` のまま渡す（整数を渡すと年として読まれる）
    return column.between(since, until)


def _alive(model, until: Stamp):
    """その時点で**まだ続いている**行（始まっていて、終わっていない）。"""
    return (or_(model.start.is_(None), model.start <= until),
            or_(model.end.is_(None), model.end > until))


# ---------------------------------------------------------------- 取り出し

def _get(session: Session, model, id_: int, label: str):
    row = session.get(model, id_)
    if row is None:
        raise NotFoundError(f"{label}={id_} という id の {model.__tablename__} が見つからない")
    return row


def _row(row, *, text: bool = True) -> dict:
    data = to_dict(row)
    if not text:
        data.pop("text", None)
    return data


def _name(session: Session, model, id_) -> str | None:
    if id_ is None:
        return None
    row = session.get(model, id_)
    return None if row is None else getattr(row, "name", None)


def _event_row(session: Session, event: Event, *, text: bool = True) -> dict:
    data = _row(event, text=text)
    data["place_name"] = _name(session, Location, event.place_id)
    data["character_name"] = _name(session, Character, event.character_id)
    data["object_name"] = _name(session, Object, event.object_id)
    return data


# ---------------------------------------------------------------- 場所の木

def descendant_place_ids(session: Session, place_id: int) -> list[int]:
    """その場所と、その配下にぶら下がる場所の id を全部返す。"""
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


def objects(session: Session, kind: str | None = None) -> list[dict]:
    """個体（群）を一覧で返す。`kind` を渡すとその種別の名前だけに絞る。"""
    query_ = select(Object)
    if kind is not None:
        query_ = query_.join(Kind, Object.kind_id == Kind.id).where(Kind.name == kind)
    rows = session.scalars(query_.order_by(Object.id.asc())).all()
    return [{"id": row.id, "name": row.name, "kind_id": row.kind_id,
              "kind_name": _name(session, Kind, row.kind_id)} for row in rows]


def kinds(session: Session) -> list[dict]:
    """種別を一覧で返す。"""
    rows = session.scalars(select(Kind).order_by(Kind.id.asc())).all()
    return [{"id": row.id, "name": row.name, "read": row.read} for row in rows]


def places(session: Session, kind: str | None = None) -> list[dict]:
    """場所を一覧で返す。`kind` を渡すとその種別だけに絞る（例: `"村"`）。"""
    query = select(Location)
    if kind is not None:
        query = query.where(Location.kind == kind)
    rows = session.scalars(query.order_by(Location.id.asc())).all()
    return [{"id": row.id, "name": row.name, "kind": row.kind,
              "parent_id": row.parent_id} for row in rows]


def place_path(session: Session, place_id: int) -> list[dict]:
    """その場所までの道筋を、上（世界線）から順に返す。"""
    chain: list[dict] = []
    seen: set[int] = set()
    current = session.get(Location, place_id)
    while current is not None and current.id not in seen:
        seen.add(current.id)
        chain.append({"id": current.id, "name": current.name, "kind": current.kind})
        current = session.get(Location, current.parent_id) if current.parent_id else None
    return list(reversed(chain))


def _up(session: Session, place_id: int, levels: int) -> int:
    """その場所から親を `levels` 段のぼった場所の id（根で止まる）。"""
    current = _get(session, Location, place_id, "place_id")
    for _ in range(max(0, levels)):
        if current.parent_id is None:
            break
        parent = session.get(Location, current.parent_id)
        if parent is None:
            break
        current = parent
    return current.id


# ---------------------------------------------------------------- 出来事

def events_at(session: Session, when, *, place_ids=None, limit=None,
              text: bool = True) -> list[dict]:
    """**その時（その幅）の出来事と行動。** 場所で絞ってもよい。"""
    since, until = span(when)
    query = select(Event).where(_in_span(Event.time, since, until))
    if place_ids is not None:
        query = query.where(Event.place_id.in_(list(place_ids)))
    query = query.order_by(Event.time.desc(), Event.id.desc())
    if limit:
        query = query.limit(limit)
    return [_event_row(session, event, text=text)
            for event in session.scalars(query).all()]


def events_of(session: Session, record_id: int, *, until=None, limit=5,
              text: bool = True) -> list[dict]:
    """**その id に掛かる出来事と行動を、新しい順に。**

    場所の id ならそこで起きたこと、人物・個体の id ならその者の行動、
    出来事の id ならそれにぶら下がる行動。
    """
    query = select(Event).where(
        or_(*[getattr(Event, column) == record_id for column in EVENT_REFS]))
    if until is not None:
        query = query.where(Event.time <= span(until)[1])
    query = query.order_by(Event.time.desc(), Event.id.desc())
    if limit:
        query = query.limit(limit)
    return [_event_row(session, event, text=text)
            for event in session.scalars(query).all()]


def _open_events(session: Session, place_ids, until: Stamp) -> list[dict]:
    """**まだ終わっていない出来事**（`end` が空か、その先）。張っているもの。"""
    query = (select(Event)
             .where(Event.place_id.in_(list(place_ids)))
             .where(Event.time <= until)
             .where(or_(Event.end.is_(None), Event.end > until))
             .where(Event.character_id.is_(None), Event.object_id.is_(None))
             .order_by(Event.time.desc(), Event.id.desc()))
    return [_event_row(session, event) for event in session.scalars(query).all()]


# ---------------------------------------------------------------- 人物・個体

def _emotions(session: Session, character_id: int, until: Stamp) -> list[dict]:
    """その時点で生きている情動（欲・恐れ・嘘・必要）。"""
    query = (select(CharacterEmotion)
             .where(CharacterEmotion.character_id == character_id)
             .where(*_alive(CharacterEmotion, until))
             .order_by(CharacterEmotion.start.desc(), CharacterEmotion.id.desc()))
    return [_row(emotion) for emotion in session.scalars(query).all()]


def _skills(session: Session, character_id: int) -> list[dict]:
    query = (select(CharacterSkill, Skill)
             .join(Skill, Skill.id == CharacterSkill.skill_id)
             .where(CharacterSkill.character_id == character_id)
             .order_by(CharacterSkill.id))
    return [{"skill_id": skill.id, "name": skill.name, "level": held.level,
             "cost": skill.cost, "effect": skill.effect, "range": skill.range,
             "duration": skill.duration, "target": skill.target,
             "constraint": skill.constraint}
            for held, skill in session.execute(query).all()]


def _place_at(session: Session, model, owner_column, owner_id: int,
              until: Stamp) -> dict | None:
    """その時点の居場所（`character_place` / `object_place` の生きている行）。"""
    query = (select(model)
             .where(owner_column == owner_id)
             .where(*_alive(model, until))
             .order_by(model.start.desc(), model.id.desc()))
    row = session.scalars(query).first()
    if row is None:
        return None
    return {"place_id": row.place_id,
            "place_name": _name(session, Location, row.place_id),
            "start": None if row.start is None else str(row.start)}


def residents(session: Session, place_ids, until: Stamp) -> tuple[list[int], list[int]]:
    """その時点でその場所（群）に居る人物と個体の id。"""
    place_ids = list(place_ids)
    character_ids = session.scalars(
        select(CharacterPlace.character_id).distinct()
        .where(CharacterPlace.place_id.in_(place_ids))
        .where(*_alive(CharacterPlace, until))).all()
    object_ids = session.scalars(
        select(ObjectPlace.object_id).distinct()
        .where(ObjectPlace.place_id.in_(place_ids))
        .where(*_alive(ObjectPlace, until))).all()
    return ([id_ for id_ in character_ids if id_ is not None],
            [id_ for id_ in object_ids if id_ is not None])


def character_sheet(session: Session, character_id: int, *, until=None,
                    count: int = 5, text: bool = True) -> dict:
    """人物一件を、**本文を書くのに要るものだけ**そろえて返す。

    口調（一人称・二人称・三人称）・性格の値・技・生きている情動・
    その時点の居場所・直近の行動。
    """
    character = _get(session, Character, character_id, "character_id")
    at = span(until)[1] if until is not None else Stamp(99999, 12, 31, 23, 59, 59)
    sheet = _row(character, text=text)
    sheet["kind_name"] = _name(session, Kind, character.kind_id)
    sheet["belong_name"] = _name(session, Object, character.belong_id)
    sheet["born_place_name"] = _name(session, Location, character.born_place_id)
    sheet["place"] = _place_at(session, CharacterPlace,
                               CharacterPlace.character_id, character_id, at)
    sheet["emotions"] = _emotions(session, character_id, at)
    sheet["skills"] = _skills(session, character_id)
    sheet["recent_events"] = events_of(
        session, character_id, until=None if until is None else at,
        limit=count, text=text)
    return sheet


def object_sheet(session: Session, object_id: int, *, until=None,
                 count: int = 5, text: bool = True) -> dict:
    """個体（群）一件。人物と同じ形でそろえる。"""
    obj = _get(session, Object, object_id, "object_id")
    at = span(until)[1] if until is not None else Stamp(99999, 12, 31, 23, 59, 59)
    sheet = _row(obj, text=text)
    sheet["kind_name"] = _name(session, Kind, obj.kind_id)
    sheet["place"] = _place_at(session, ObjectPlace, ObjectPlace.object_id,
                               object_id, at)
    sheet["recent_events"] = events_of(
        session, object_id, until=at, limit=count, text=text)
    return sheet


# ---------------------------------------------------------------- 作品

def story_digest(session: Session, story: Story) -> dict:
    """作品一件の見出し。話数・未同期の数まで含める。"""
    episodes = session.scalars(
        select(Episode).where(Episode.story_id == story.id)
        .order_by(Episode.number)).all()
    digest = _row(story)
    digest["world_name"] = _name(session, Location, story.world_id)
    digest["place_name"] = _name(session, Location, story.place_id)
    digest["episode_count"] = len(episodes)
    digest["last_episode"] = episodes[-1].number if episodes else None
    digest["unsynced"] = [episode.number for episode in episodes if not episode.synced]
    return digest


def stories(session: Session) -> list[dict]:
    return [story_digest(session, story)
            for story in session.scalars(select(Story).order_by(Story.id)).all()]


def episodes(session: Session, story_id: int, *, count: int = 10, before=None,
             text: bool = True) -> list[dict]:
    """**直前の `count` 話を、古い順に並べて返す。**

    `before` を渡すと、その話数より前の `count` 話。`text=False` なら
    話数と題だけ（一覧を見るとき）。
    """
    _get(session, Story, story_id, "story_id")
    query = select(Episode).where(Episode.story_id == story_id)
    if before is not None:
        query = query.where(Episode.number < int(before))
    rows = session.scalars(
        query.order_by(Episode.number.desc()).limit(count)).all()
    return [_row(episode, text=text) for episode in reversed(rows)]


def unsynced_episodes(session: Session, story_id: int | None = None) -> list[dict]:
    """**同期フラグの下りている話。** 一件でも残っていればモード 3 が先。"""
    query = select(Episode).where(Episode.synced.is_(False))
    if story_id is not None:
        query = query.where(Episode.story_id == story_id)
    rows = session.scalars(query.order_by(Episode.story_id, Episode.number)).all()
    return [{"id": episode.id, "story_id": episode.story_id,
             "story_name": _name(session, Story, episode.story_id),
             "number": episode.number, "title": episode.title}
            for episode in rows]


# ---------------------------------------------------------------- 断面と顔ぶれ

def brief(session: Session, place_id: int, when=None, *, reach: int = 60,
          full: bool = False) -> dict:
    """**世界がいまどうなっているか**（断面）を一枚にまとめる。

    その場所の道筋、配下で張っている出来事、`reach` 年ぶんの直近の出来事、
    そこで使われる語、いま居る者の名前。

    `full=False`（既定）では裏の種別（`裏` `伏線`）を伏せる。
    住人が知らないことを本文に書かないため。
    """
    location = _get(session, Location, place_id, "place_id")
    if when is None:
        raise ValueError("時刻が決まらない（when を渡す）")
    since, until = span(when)
    place_ids = descendant_place_ids(session, place_id)

    def visible(rows):
        if full:
            return rows
        return [row for row in rows if row.get("kind") not in HIDDEN_EVENT_KINDS]

    recent_query = (select(Event)
                    .where(Event.place_id.in_(place_ids))
                    .where(Event.time <= until)
                    .where(Event.time >= Stamp(max(1, since.year - reach)))
                    .order_by(Event.time.desc(), Event.id.desc()))
    recent = [_event_row(session, event)
              for event in session.scalars(recent_query).all()]

    character_ids, object_ids = residents(session, place_ids, until)
    terms = session.scalars(
        select(Term).where(or_(Term.restrict_place_id.in_(place_ids),
                               Term.restrict_planet_id.in_(place_ids),
                               Term.restrict_world_id.in_(place_ids),
                               Term.restrict_place_id.is_(None)))
        .order_by(Term.id)).all()

    return {
        "place": _row(location),
        "path": place_path(session, place_id),
        "time": str(until),
        "reach": reach,
        "open_events": visible(_open_events(session, place_ids, until)),
        "recent_events": visible(recent),
        "terms": [{"id": term.id, "name": term.name, "kind": term.kind,
                   "text": term.text} for term in terms],
        "present_characters": [
            {"id": id_, "name": _name(session, Character, id_)}
            for id_ in character_ids],
        "present_objects": [
            {"id": id_, "name": _name(session, Object, id_)}
            for id_ in object_ids],
    }


def cast(session: Session, story_id: int, when=None, *, count: int = 5,
         levels: int = 1) -> dict:
    """**その話に出せる顔ぶれ。**

    作品の立つ場所から `levels` 段のぼったところを基準に、その配下に
    その時点で居る人物と個体を集め、一人（一群）ずつ直近 `count` 件の
    出来事を添える。隣の集落にいる者も枠に入れるため、既定で一段のぼる。
    """
    story = _get(session, Story, story_id, "story_id")
    if story.place_id is None:
        raise ValueError(f"作品 {story.name} に立つ場所（place_id）が無い")
    _, until = resolve_time(session, when, story)
    root_id = _up(session, story.place_id, levels)
    place_ids = descendant_place_ids(session, root_id)
    character_ids, object_ids = residents(session, place_ids, until)
    return {
        "story": {"id": story.id, "name": story.name},
        "time": str(until),
        "scope": {"id": root_id, "name": _name(session, Location, root_id),
                  "path": place_path(session, root_id)},
        "characters": [
            character_sheet(session, id_, until=until, count=count, text=False)
            for id_ in character_ids],
        "objects": [
            object_sheet(session, id_, until=until, count=count, text=False)
            for id_ in object_ids],
    }
