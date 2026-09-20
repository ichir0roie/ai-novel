#!/usr/bin/env python3
"""**世界の側の人物を、時の流れの中で自動的に増やす。**

`DEM.local_ai.time_keepr.main` の常駐ループから毎日呼ばれる。
「1月に一度、月初に、10%の確率で」新しい人物が一件生まれる。

`random_location_generator` と同じ理由で、claude を介さず db への確定まで
一度に行う。名前・読み・口調・出自といった AI の判断が要る欄だけを
ローカルAI（`ai_client`）に委ねる。
"""
from __future__ import annotations

import random

from sqlalchemy import select

from DEM.db.schema import Character, Kind, Location, Session, Stamp
from DEM.local_ai import ai_client
from DEM.randomizer.random_character_generator import build_character

PROBABILITY = 0.10  # 1月に1度、10%の確率で

_SYSTEM_PROMPT = (
    "あなたは架空の世界観を構築する設定作家です。"
    "新しく生まれる人物1件について、名前・読み・簡単な人物説明を、"
    "日本的な漢字（訓読み）・ひらがな・カタカナで名づけた、"
    "自然な固有名詞で JSON で答えてください。"
    "キーは name（名前）, read（読み）, text（一言で分かる人物説明）の三つだけ。"
)


def _should_roll(time: Stamp) -> bool:
    """月に一度、月初（1日）にだけロールする。"""
    return time.day == 1


def generate_random(session: Session, time: Stamp) -> Character | None:
    """ロールに当たったら、人物を一件 db へ確定して返す。当たらなければ None。"""
    if not _should_roll(time):
        return None

    seed = random.randrange(10 ** 9)
    rng = random.Random(seed)
    print(f"[time_keepr/character] seed={seed}")
    if rng.random() >= PROBABILITY:
        return None

    places = session.scalars(select(Location)).all()
    kinds = session.scalars(select(Kind)).all()
    born_place = rng.choice(places) if places else None
    kind = rng.choice(kinds) if kinds else None

    draft = build_character(
        born_place_id=born_place.id if born_place else None,
        kind_id=kind.id if kind else None,
    )

    prompt = (
        f"生まれの場所: {born_place.name if born_place else '不明'}"
        f"（{born_place.kind if born_place else '-'}）\n"
        f"種別: {kind.name if kind else '不明'}\n"
        f"性別: {draft['sex']} / 体格: {draft['build']} / 口調: {draft['tone']}\n"
        f"現在の時刻: {time}\n"
        "この場所・種別に自然な人物を1件、決めてください。"
    )
    decided = ai_client.generate_json(prompt, system=_SYSTEM_PROMPT)

    draft["name"] = decided.get("name") or draft["name"]
    draft["read"] = decided.get("read") or draft["read"]
    draft["text"] = decided.get("text") or draft["text"]
    draft["start"] = time

    record = Character(**draft)
    session.add(record)
    session.commit()
    print(f"[time_keepr/character] 生成: {record.name}（{record.read}）"
          f" born_place_id={record.born_place_id} kind_id={record.kind_id}")
    return record
