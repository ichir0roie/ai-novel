#!/usr/bin/env python3
"""**世界の側の場所を、時の流れの中で自動的に増やす。**

`DEM.local_ai.time_keepr.main` の常駐ループから毎日呼ばれる。
「1年に一度、年初に、1%の確率で」新しい場所が一件生まれる。

`DEM/claude_interface/randomizer/` の create → commit の二段は、claude が
対話の中で下書きを見てから確定する前提の設計だが、この常駐ループは claude
を介さず回り続ける必要があるため、ここでは db への確定まで一度に行う
（AIの判断が要る「名前・種別・親」の決定だけをローカルAI（`ai_client`）に
委ねる）。
"""
from __future__ import annotations

import random

from sqlalchemy import select

from DEM.db.schema import Location, Session, Stamp
from DEM.local_ai import ai_client
from DEM.randomizer.random_location_generator import build_location

PROBABILITY = 0.01  # 1年に1度、1%の確率で

_SYSTEM_PROMPT = (
    "あなたは架空の世界観を構築する設定作家です。"
    "既存の場所の一覧と、新しく生まれる場所がどこの配下になりそうかを渡します。"
    "その配下に新しく生まれる場所を1件だけ考え、日本的な漢字（訓読み）・"
    "ひらがな・カタカナで名づけた、自然な固有名詞を JSON で答えてください。"
    "キーは name（固有名詞）, kind（大陸/国/町/村などの種別）,"
    " text（一言で分かる地理・文化の説明）の三つだけ。"
)


def _should_roll(time: Stamp) -> bool:
    """年に一度、年初（1月1日）にだけロールする。"""
    return time.month == 1 and time.day == 1


def generate_random(session: Session, time: Stamp) -> Location | None:
    """ロールに当たったら、場所を一件 db へ確定して返す。当たらなければ None。"""
    if not _should_roll(time):
        return None

    seed = random.randrange(10 ** 9)
    rng = random.Random(seed)
    print(f"[time_keepr/location] seed={seed}")
    if rng.random() >= PROBABILITY:
        return None

    candidates = session.scalars(select(Location)).all()
    parent = rng.choice(candidates) if candidates else None

    draft = build_location(parent_id=parent.id if parent else None)

    prompt = (
        f"既存の場所（id, 名前, 種別）: "
        f"{[(c.id, c.name, c.kind) for c in candidates[:50]]}\n"
        f"新しい場所の親: {parent.id if parent else 'なし（根の場所）'}"
        f"（{parent.name if parent else '-'}, {parent.kind if parent else '-'}）\n"
        f"現在の時刻: {time}\n"
        "この親の配下に新しく生まれる場所を1件、決めてください。"
    )
    decided = ai_client.generate_json(prompt, system=_SYSTEM_PROMPT)

    draft["name"] = decided.get("name") or draft["name"]
    draft["kind"] = decided.get("kind") or draft["kind"]
    draft["text"] = decided.get("text") or draft["text"]
    draft["parent_id"] = parent.id if parent else None
    draft["start"] = time

    record = Location(**draft)
    session.add(record)
    session.commit()
    print(f"[time_keepr/location] 生成: {record.name}（{record.kind}）"
          f" parent_id={record.parent_id}")
    return record
