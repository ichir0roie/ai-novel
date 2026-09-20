#!/usr/bin/env python3
"""**その時点で生きている人物・個体に、日々の出来事を起こす。**

`DEM.local_ai.time_keepr.main` の常駐ループから毎日呼ばれる。
`random_character_generator` `random_location_generator` と同じ理由で、
claude を介さず db への確定まで一度に行う(内容の判断だけをローカル
AI(`ai_client`)に委ねる)。

「1月に一度、月初に、生きている人物・個体それぞれについて一定の確率で」
出来事を一件起こす。人物に起きた出来事には、`DEM/claude_interface/
randomizer/commit_event.py` の `character_drives` `character_skills` と
同じ形で、情動(`CharacterEmotion`。テーブル名は `character_drive`)の
変化と技(`CharacterSkill`)の熟練度もその場でまとめて記録する
(個体には情動・技の欄が無いので、個体の出来事はそこまでで止める)。

技は**新しく作らない**。名づけ(`IHG/naming.md`)が要る判断なので、
既にある技(`Skill`)の中から AI に選ばせるだけにとどめる。当てはまる
ものが無ければ、その出来事の技の伸びは見送る。
"""
from __future__ import annotations

import random

from sqlalchemy import select

from DEM.data_access_logic.query import (
    character_simulation_query, common_query, world_createion_query,
)
from DEM.db.schema import (
    Character, CharacterEmotion, CharacterSkill, Event, EventCharacter,
    EventObject, Object, Session, Skill, Stamp,
)
from DEM.local_ai import ai_client
from DEM.local_ai.time_keepr._format import format_time

CHARACTER_PROBABILITY = 0.10  # 月に一度、生きている人物1人につき10%の確率で
OBJECT_PROBABILITY = 0.05  # 月に一度、生きている個体1件につき5%の確率で

_CHARACTER_SYSTEM_PROMPT = (
    "あなたは架空の世界観の中で、人物の日々を描写する設定作家です。"
    "人物の情報と周囲の状況を渡すので、この時点でその人物に起きる出来事を"
    "1件だけ考えてください。JSON で答えてください。キーは "
    "event_name(出来事の名前), event_kind(出来事の種別。一言。"
    "無ければ空文字), event_text(出来事の内容。一言), "
    "drive_text(この出来事で動いた情動・欲求。無ければ空文字), "
    "drive_level(その情動の強さ。1〜10の整数。無ければ0), "
    "skill_name(この出来事で伸びた技の名前。渡した技の候補の中からだけ選ぶ。"
    "当てはまるものが無ければ空文字), "
    "skill_level(その技の熟練度。1〜10の整数。無ければ0)の七つだけ。"
)

_OBJECT_SYSTEM_PROMPT = (
    "あなたは架空の世界観の中で、個体(群)の日々を描写する設定作家です。"
    "個体の情報と周囲の状況を渡すので、この時点でその個体に起きる出来事を"
    "1件だけ考えてください。JSON で答えてください。キーは "
    "event_name(出来事の名前), event_kind(出来事の種別。一言。"
    "無ければ空文字), event_text(出来事の内容。一言)の三つだけ。"
)


def _should_roll(time: Stamp) -> bool:
    """月に一度、月初(1日)にだけロールする。"""
    return time.day == 1


def _current_place_id(session: Session, character: Character, time: Stamp) -> int | None:
    place = session.scalars(
        common_query.character_place_select(character.id, time)).first()
    return place.location_id if place else character.born_place_id


def _progress_character(
    session: Session, character: Character, time: Stamp,
) -> Event | None:
    place_id = _current_place_id(session, character, time)

    # `read_surroundings`(claude_interface)と同じ、人物を軸にした周辺取得。
    # 居合わせる人物・個体と、直近の出来事を一度に取る。
    companions, nearby_objects, recent_events = (
        character_simulation_query.character_around_event(session, character.id, time)
    )
    companions = [c for c in companions if c.id != character.id]

    drives = session.scalars(common_query.emotions_select(character.id, time)).all()
    skills = session.scalars(common_query.skills_select(character.id)).all()
    catalog = session.scalars(select(Skill)).all()
    known_skill_names = {s.skill.name for s in skills if s.skill} | {s.name for s in catalog}

    prompt = (
        f"人物: {character.name}(id={character.id}, 口調={character.tone})\n"
        f"現在の場所id: {place_id if place_id is not None else '不明'}\n"
        f"居合わせる人物: {[(c.id, c.name) for c in companions[:20]]}\n"
        f"居合わせる個体: {[(o.id, o.name) for o in nearby_objects[:20]]}\n"
        f"直近の出来事: {[e.name for e in recent_events[:10]]}\n"
        f"今の情動: {[(d.text, d.level) for d in drives]}\n"
        f"今の技: {[(s.skill.name, s.level) for s in skills if s.skill]}\n"
        f"選べる技の候補: {sorted(known_skill_names)}\n"
        f"現在の時刻: {time}\n"
        "この人物に、この時点で起きる出来事を1件、決めてください。"
    )
    decided = ai_client.try_generate_json(prompt, system=_CHARACTER_SYSTEM_PROMPT)

    if not decided.get("event_name"):
        return None

    record = Event(
        name=decided["event_name"],
        kind=decided.get("event_kind") or "",
        text=decided.get("event_text") or "",
        time=time,
        place_id=place_id,
    )
    record.event_characters = [EventCharacter(character_id=character.id)]
    session.add(record)

    drive_text = decided.get("drive_text")
    if drive_text:
        session.add(CharacterEmotion(
            character_id=character.id, text=drive_text,
            level=int(decided.get("drive_level") or 1),
            start=time, end=None,
        ))

    skill_name = decided.get("skill_name")
    if skill_name:
        skill = session.scalar(select(Skill).where(Skill.name == skill_name))
        if skill is not None:
            session.add(CharacterSkill(
                character_id=character.id, skill_id=skill.id,
                level=int(decided.get("skill_level") or 1),
            ))
        else:
            print(f"[time_keepr/event] 既存に無い技名 {skill_name!r} は見送り")

    session.commit()
    when = format_time(time)
    print(f"[time_keepr/event] {when} 人物 {character.name}(id={character.id}): "
          f"{record.name}({record.kind}) {record.text}"
          + (f" / 情動: {drive_text}" if drive_text else "")
          + (f" / 技: {skill_name}" if skill_name else ""))
    return record


def _progress_object(
    session: Session, obj: Object, time: Stamp,
) -> Event | None:
    place = session.scalars(common_query.object_place_select(obj.id, time)).first()
    place_id = place.location_id if place else obj.root_place_name

    prompt = (
        f"個体: {obj.name}(id={obj.id})\n"
        f"現在の場所id: {place_id if place_id is not None else '不明'}\n"
        f"現在の時刻: {time}\n"
        "この個体に、この時点で起きる出来事を1件、決めてください。"
    )
    decided = ai_client.try_generate_json(prompt, system=_OBJECT_SYSTEM_PROMPT)

    if not decided.get("event_name"):
        return None

    record = Event(
        name=decided["event_name"],
        kind=decided.get("event_kind") or "",
        text=decided.get("event_text") or "",
        time=time,
        place_id=place_id,
    )
    record.event_objects = [EventObject(object_id=obj.id)]
    session.add(record)
    session.commit()
    when = format_time(time)
    print(f"[time_keepr/event] {when} 個体 {obj.name}(id={obj.id}): "
          f"{record.name}({record.kind}) {record.text}")
    return record


def generate_random(session: Session, time: Stamp) -> list[Event]:
    """月初に、生きている人物・個体それぞれについて出来事を進行させる。"""
    if not _should_roll(time):
        return []

    seed = random.randrange(10 ** 9)
    rng = random.Random(seed)
    created: list[Event] = []

    characters = session.scalars(
        world_createion_query.alive_characters_select(time)).all()
    total_characters = len(characters)
    for i, character in enumerate(characters, start=1):
        print(f"[time_keepr/event] 人物 {i}/{total_characters}: {character.name}(id={character.id})")
        if rng.random() < CHARACTER_PROBABILITY:
            event = _progress_character(session, character, time)
            if event is not None:
                created.append(event)

    objects = session.scalars(
        world_createion_query.alive_objects_select(time)).all()
    total_objects = len(objects)
    for i, obj in enumerate(objects, start=1):
        print(f"[time_keepr/event] 個体 {i}/{total_objects}: {obj.name}(id={obj.id})")
        if rng.random() < OBJECT_PROBABILITY:
            event = _progress_object(session, obj, time)
            if event is not None:
                created.append(event)

    return created
