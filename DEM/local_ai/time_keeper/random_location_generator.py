#!/usr/bin/env python3
"""世界の側の場所を、時の流れの中で自動的に増やす。年初に確率 `constants.LOCATION_PROBABILITY` で一件生まれ、db へ確定する。"""
from __future__ import annotations

import random

from DEM.ai_instructions.naming import PLACE_NAMING_INSTRUCTION
from DEM.data_access_logic.query import world_createion_query
from DEM.data_access_logic.query.base import location_active_condition
from DEM.db.schema import Location, Session, Stamp
from DEM.local_ai import ai_client
from DEM.local_ai.time_keeper import constants
from DEM.local_ai.time_keeper._format import format_time
from DEM.randomizer.random_location_generator import build_location

_SYSTEM_PROMPT = (
    "あなたは架空の世界観を構築する設定作家です。"
    "既存の場所の一覧と、新しく生まれる場所がどこの配下になりそうかを渡します。"
    "その配下に新しく生まれる場所を1件だけ考え、自然な固有名詞を JSON で"
    "答えてください。" + PLACE_NAMING_INSTRUCTION + "キーは name(固有名詞), "
    "kind(大陸/国/町/村などの種別), text(具体的な産業・生活・人間関係が"
    "伝わる2〜3文の説明。「自然豊か」「歴史がある」のような、他のどの場所"
    "にも当てはまる抽象的な形容だけで済ませず、この場所固有の職業・特産品・"
    "行事・地形の起伏など具体を最低一つ含める), environment(環境。気候・"
    "地形など一言)の四つだけ。"
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "kind": {"type": "string"},
        "text": {"type": "string"},
        "environment": {"type": "string"},
    },
    "required": ["name", "kind", "text", "environment"],
    "additionalProperties": False,
}


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
    if roll >= constants.LOCATION_PROBABILITY:
        print(f"[time_keepr/location] {when} 年初判定: "
              f"seed={seed} roll={roll:.4f} >= {constants.LOCATION_PROBABILITY} → 見送り")
        return None
    print(f"[time_keepr/location] {when} 年初判定: "
          f"seed={seed} roll={roll:.4f} < {constants.LOCATION_PROBABILITY} → 生成")

    # 親は、この時刻にまだ存在している(start〜end に収まっている)場所だけ。
    candidates = session.scalars(
        world_createion_query.alive_locations_select(time)
        .where(location_active_condition())).all()
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

    draft = build_location(
        parent_id=parent.id if parent else None, area=area,
        active_random_generation=parent.active_random_generation if parent else False)

    prompt = (
        f"既存の場所(id, 名前, 種別): "
        f"{[(c.id, c.name, c.kind) for c in candidates[:50]]}\n"
        f"新しい場所の親: {parent.id if parent else 'なし(根の場所)'}"
        f"({parent.name if parent else '-'}, {parent.kind if parent else '-'})\n"
        f"現在の時刻: {time}\n"
        "この親の配下に新しく生まれる場所を1件、決めてください。"
    )
    decided = ai_client.try_generate_json(prompt, _SCHEMA, system=_SYSTEM_PROMPT)

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

    return record
