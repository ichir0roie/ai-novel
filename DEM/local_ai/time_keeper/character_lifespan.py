#!/usr/bin/env python3
"""**人物に寿命を持たせ、老いと事故で `Character.end` を下ろす。**

`DEM.local_ai.time_keeper.main` の常駐ループから毎日呼ばれる。

人物を作る時点(`random_character_generator`)では `end` を決めない。代わりに
ここで、生きている人物一人ひとりについて年齢に応じた確率を毎年ロールし、
当たったら寿命(老衰)で `end` を下ろす。老衰とは別に、ごく低い確率で
年齢によらない事故死もロールする。

死んだ人物には、老衰・事故それぞれの死を場面として書いた `Event` を一件
起こす(`_progress_place` と同じ基準。要約で済ませず場面で書く)。
"""
from __future__ import annotations

import random

from DEM.ai_instructions.event_writing import EVENT_SCENE_INSTRUCTION
from DEM.data_access_logic.query import common_query, world_createion_query
from DEM.db.schema import Character, Event, EventCharacter, Session, Stamp
from DEM.local_ai import ai_client
from DEM.local_ai.time_keeper._format import format_time

# 老衰。この歳を過ぎるまでは自然死しない。
_NATURAL_DEATH_MIN_AGE = 50
# この歳に達したら、老衰は必ず起きる(不老でない限り)。
_NATURAL_DEATH_MAX_AGE = 150

# 事故。年齢によらず、年に一度この確率で起きうる(不死でない限り)。
_ACCIDENT_PROBABILITY_PER_YEAR = 0.003

_DEATH_SYSTEM_PROMPT = (
    "あなたは架空の世界観の中で、ある人物の死を描く設定作家です。"
    "渡す人物の情報と死因をもとに、その最期を1件だけ場面として考えてください。"
    + EVENT_SCENE_INSTRUCTION +
    "JSON で答えてください。キーは event_name(出来事の名前), "
    "event_text(死の場面)の二つだけ。"
)


def _should_roll(time: Stamp) -> bool:
    """年に一度、元日(1月1日)にだけロールする。"""
    return time.month == 1 and time.day == 1


def _natural_death_probability(age: int) -> float:
    """老衰の年間確率。`_NATURAL_DEATH_MIN_AGE` 未満は 0、
    `_NATURAL_DEATH_MAX_AGE` 以上は必ず死ぬよう 1 まで線形に上げる。
    """
    if age < _NATURAL_DEATH_MIN_AGE:
        return 0.0
    if age >= _NATURAL_DEATH_MAX_AGE:
        return 1.0
    span = _NATURAL_DEATH_MAX_AGE - _NATURAL_DEATH_MIN_AGE
    return (age - _NATURAL_DEATH_MIN_AGE) / span


def _current_place_id(session: Session, character: Character, time: Stamp) -> int | None:
    place = session.scalars(
        common_query.character_place_select(character.id, time)).first()
    return place.location_id if place else character.born_place_id


def _kill(
    session: Session, character: Character, time: Stamp, cause: str,
) -> Event:
    place_id = _current_place_id(session, character, time)
    prompt = (
        f"人物: {character.name}(id={character.id})。{character.text or ''}\n"
        f"死因: {cause}\n"
        f"歳: {time.year - character.start.year if character.start else '不明'}\n"
        f"現在の時刻: {time}\n"
        "この人物の最期を1件、決めてください。"
    )
    decided = ai_client.try_generate_json(prompt, system=_DEATH_SYSTEM_PROMPT)

    character.end = time

    record = Event(
        name=decided.get("event_name") or f"{character.name}の死({cause})",
        kind="死",
        text=decided.get("event_text") or "",
        time=time,
        location_id=place_id,
    )
    record.event_characters = [EventCharacter(character_id=character.id)]
    session.add(record)
    session.commit()

    when = format_time(time)
    print(f"[time_keepr/lifespan] {when} {character.name}(id={character.id}) "
          f"死亡({cause}): {record.name}")
    return record


def generate_random(session: Session, time: Stamp) -> list[Event]:
    """年初に、生きている人物それぞれの老衰・事故をロールする。"""
    if not _should_roll(time):
        return []

    created: list[Event] = []
    characters = session.scalars(
        world_createion_query.alive_characters_select(time)).all()

    for character in characters:
        if character.start is None:
            continue

        age = time.year - character.start.year

        if _NATURAL_DEATH_MAX_AGE < age:
            dead_age = random.randint(_NATURAL_DEATH_MAX_AGE, age)
            dead_time = Stamp(character.start.year + dead_age)
            created.append(_kill(session, character, dead_time, "老衰"))

        if random.random() < _natural_death_probability(age):
            created.append(_kill(session, character, time, "老衰"))
            continue

        if random.random() < _ACCIDENT_PROBABILITY_PER_YEAR:
            created.append(_kill(session, character, time, "事故"))

    return created
