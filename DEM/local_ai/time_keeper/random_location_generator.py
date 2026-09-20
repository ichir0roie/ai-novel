#!/usr/bin/env python3
"""**世界の側の場所を、時の流れの中で自動的に増やす。**

`DEM.local_ai.time_keepr.main` の常駐ループから毎日呼ばれる。
「1年に一度、年初に、1%の確率で」新しい場所が一件生まれる。

`DEM/claude_interface/randomizer/` の create → commit の二段は、claude が
対話の中で下書きを見てから確定する前提の設計だが、この常駐ループは claude
を介さず回り続ける必要があるため、ここでは db への確定まで一度に行う
(AIの判断が要る「名前・種別・親」の決定だけをローカルAI(`ai_client`)に
委ねる)。
"""
from __future__ import annotations

import random

from DEM.data_access_logic.query import world_createion_query
from DEM.db.schema import Location, Session, Stamp
from DEM.local_ai import ai_client
from DEM.local_ai.time_keeper import random_location_resource_generator
from DEM.local_ai.time_keeper._format import format_time
from DEM.randomizer.random_location_generator import build_location

PROBABILITY = 0.01  # 1年に1度、1%の確率で

_SYSTEM_PROMPT = (
    "あなたは架空の世界観を構築する設定作家です。"
    "既存の場所の一覧と、新しく生まれる場所がどこの配下になりそうかを渡します。"
    "その配下に新しく生まれる場所を1件だけ考え、日本的な漢字(訓読み)・"
    "ひらがな・カタカナで名づけた、自然な固有名詞を JSON で答えてください。"
    "キーは name(固有名詞), kind(大陸/国/町/村などの種別),"
    " text(一言で分かる地理・文化の説明), environment(環境。気候・地形など"
    "一言)の四つだけ。"
)


def _remaining_area(session: Session, parent: Location) -> float | None:
    """`parent` の配下に、あとどれだけ広さを割り当てられるか。

    `parent.area` が無ければ制約なし(`None`)。あれば、
    `親の広さ - 既にある兄弟の広さの合計` を返す(0 以下ならもう入らない)。
    """
    if parent.area is None:
        return None
    siblings_area = session.scalar(
        world_createion_query.siblings_area_sum_select(parent.id))
    return float(parent.area) - float(siblings_area)


def _should_roll(time: Stamp) -> bool:
    """年に一度、年初(1月1日)にだけロールする。"""
    return time.month == 1 and time.day == 1


def generate_random(session: Session, time: Stamp) -> Location | None:
    """ロールに当たったら、場所を一件 db へ確定して返す。当たらなければ None。"""
    if not _should_roll(time):
        return None

    seed = random.randrange(10 ** 9)
    rng = random.Random(seed)
    roll = rng.random()
    when = format_time(time)
    if roll >= PROBABILITY:
        print(f"[time_keepr/location] {when} 年初判定: "
              f"seed={seed} roll={roll:.4f} >= {PROBABILITY} → 見送り")
        return None
    print(f"[time_keepr/location] {when} 年初判定: "
          f"seed={seed} roll={roll:.4f} < {PROBABILITY} → 生成")

    # 親は、この時刻にまだ存在している(start〜end に収まっている)場所だけ。
    candidates = session.scalars(
        world_createion_query.alive_locations_select(time)).all()
    # 広さが決まっている親は、もう入る余地(remaining > 0)がある場所だけを選ぶ。
    # 広さが決まっていない親(None)は制約が無いのでそのまま選べる。
    eligible = [
        c for c in candidates
        if (remaining := _remaining_area(session, c)) is None or remaining > 0
    ]
    if candidates and not eligible:
        print(f"[time_keepr/location] {when} 広さの余地がある親が無いため見送り")
        return None
    parent = rng.choice(eligible) if eligible else None

    area = None
    remaining = _remaining_area(session, parent) if parent else None
    if remaining is not None:
        # 親の広さを超えないよう、余地の一部だけを割り当てる
        # (兄弟がまだ増える余地を残すため、余地全部は使わない)。
        area = rng.uniform(remaining * 0.05, remaining * 0.5)

    draft = build_location(parent_id=parent.id if parent else None, area=area)

    prompt = (
        f"既存の場所(id, 名前, 種別): "
        f"{[(c.id, c.name, c.kind) for c in candidates[:50]]}\n"
        f"新しい場所の親: {parent.id if parent else 'なし(根の場所)'}"
        f"({parent.name if parent else '-'}, {parent.kind if parent else '-'})\n"
        f"現在の時刻: {time}\n"
        "この親の配下に新しく生まれる場所を1件、決めてください。"
    )
    decided = ai_client.try_generate_json(prompt, system=_SYSTEM_PROMPT)

    draft["name"] = decided.get("name") or draft["name"]
    draft["kind"] = decided.get("kind") or draft["kind"]
    draft["text"] = decided.get("text") or draft["text"]
    draft["environment"] = decided.get("environment") or draft["environment"]
    draft["parent_id"] = parent.id if parent else None
    draft["start"] = time

    record = Location(**draft)
    session.add(record)
    session.commit()
    parent_label = f"{parent.name}(id={parent.id})" if parent else "根(親なし)"
    print(f"[time_keepr/location] {when} 生成: {record.name}({record.kind})"
          f" id={record.id} 親={parent_label} 広さ={record.area} 環境={record.environment}\n"
          f"    説明: {record.text or '(説明なし)'}")

    random_location_resource_generator.generate_for_new_location(session, record, time)
    return record
