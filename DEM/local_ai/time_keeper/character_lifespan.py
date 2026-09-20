#!/usr/bin/env python3
"""**人物に寿命を持たせ、老いと事故で `Character.end` を下ろす。**

`DEM.local_ai.time_keeper.main` の常駐ループから毎日呼ばれる。

人物を作る時点(`random_character_generator`)では `end` を決めない。代わりに
ここで、生きている人物一人ひとりについて年齢に応じた確率を毎年ロールし、
当たったら寿命(老衰)で `end` を下ろす。老衰とは別に、ごく低い確率で
年齢によらない事故死もロールする。

**技「不老」「不死」による免除**(`_AGELESS_SKILL` `_IMMORTAL_SKILL`)。
「不死」を持つ人物は老衰・事故のどちらでも死なない。「不老」は老衰では
死なないが、事故では死にうる。どちらも `DEM/claude_interface/randomizer/
commit_character_skill.py`(または `commit_event` の `character_skills`)で
出来事の結果として後から付与される想定なので、生成時点でのスキル有無は
問わず、ロールのたびに現在のスキルを見る。

死んだ人物には、老衰・事故それぞれの死を場面として書いた `Event` を一件
起こす(`_progress_place` と同じ基準。要約で済ませず場面で書く)。
"""
from __future__ import annotations

import random

from sqlalchemy import select

from DEM.data_access_logic.query import common_query, world_createion_query
from DEM.db.schema import Character, CharacterSkill, Event, EventCharacter, Session, Skill, Stamp
from DEM.local_ai import ai_client
from DEM.local_ai.time_keeper._format import format_time

_AGELESS_SKILL = "不老"  # 老衰では死なない。事故では死にうる
_IMMORTAL_SKILL = "不死"  # 老衰・事故のどちらでも死なない

# 老衰。この歳を過ぎるまでは自然死しない。
_NATURAL_DEATH_MIN_AGE = 50
# この歳に達したら、老衰は必ず起きる(不老でない限り)。
_NATURAL_DEATH_MAX_AGE = 150

# 事故。年齢によらず、年に一度この確率で起きうる(不死でない限り)。
_ACCIDENT_PROBABILITY_PER_YEAR = 0.003

_DEATH_SYSTEM_PROMPT = (
    "あなたは架空の世界観の中で、ある人物の死を描く設定作家です。"
    "渡す人物の情報と死因をもとに、その最期を1件だけ場面として考えてください。"
    "要約(「〜という出来事があった」)で済ませない。軽い小説として1000文字"
    "程度で、その時その場の思考・行動・周囲への影響を場面として書く。"
    "JSON で答えてください。キーは event_name(出来事の名前), "
    "event_text(死の場面)の二つだけ。"
)


def _should_roll(time: Stamp) -> bool:
    """年に一度、元日(1月1日)にだけロールする。"""
    return time.month == 1 and time.day == 1


def _skill_names(session: Session, character_id: int) -> set[str]:
    rows = session.execute(
        select(Skill.name)
        .join(CharacterSkill, CharacterSkill.skill_id == Skill.id)
        .where(CharacterSkill.character_id == character_id)
    ).all()
    return {name for (name,) in rows}


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
        place_id=place_id,
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
        skills = _skill_names(session, character.id)
        if _IMMORTAL_SKILL in skills:
            continue

        age = time.year - character.start.year

        if _NATURAL_DEATH_MAX_AGE < age:
            dead_age = random.randint(age, _NATURAL_DEATH_MAX_AGE)
            dead_time = Stamp(character.start+dead_age)
            created.append(_kill(session, character, dead_time, "老衰"))

        if _AGELESS_SKILL not in skills:
            if random.random() < _natural_death_probability(age):
                created.append(_kill(session, character, time, "老衰"))
                continue

        if random.random() < _ACCIDENT_PROBABILITY_PER_YEAR:
            created.append(_kill(session, character, time, "事故"))

    return created
