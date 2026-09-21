#!/usr/bin/env python3
"""世界の側の個体(国・組織・商会などの群)を、時の流れの中で自動的に増やす。

月初に確率 `PROBABILITY` で、人物が居てプロットのある場所を選び、個体を一件生んで db へ確定する。
"""
from __future__ import annotations

import random

from DEM.ai_instructions.naming import TERM_NAMING_INSTRUCTION
from DEM.ai_instructions.principles import AVOID_NARO_TEMPLATE_INSTRUCTION
from DEM.data_access_logic.query import common_query, story_createion_query, world_createion_query
from DEM.db.schema import Location, Object, ObjectPlace, Session, Stamp
from DEM.local_ai import ai_client
from DEM.local_ai.time_keeper._format import format_time
from DEM.randomizer.random_object_generator import build_object

PROBABILITY = 0.15  # 1月に1度、15%の確率で

# AI に選ばせる「どこまで届く群か」と、それを落とす world_influence の値。
# 数そのものを AI に決めさせない(尺度が決まっていないため)。
_SCALE_INFLUENCE = {
    "集落内": 0,
    "地域": 1,
    "国": 2,
    "大陸": 3,
}
_DEFAULT_SCALE = "地域"

_SYSTEM_PROMPT = (
    "あなたは架空の世界観を構築する設定作家です。"
    "ある場所と、そこに居る人物・既にある群を渡すので、この場所を拠り所に"
    "生まれる群(国・組織・商会・氏族・徒党など、まとまりとして動くもの)を"
    "1件だけ考えてください。"
    + TERM_NAMING_INSTRUCTION +
    "組織の名は「〜機構」「〜管理局」のような硬い漢語で止めず、場所名か"
    "役割名で呼べる形にする。"
    "既にある群と役割が重なるものは作らない。"
    + AVOID_NARO_TEMPLATE_INSTRUCTION +
    "JSON で答えてください。キーは name(群の名), read(読み), "
    "text(この群が何であって、何を決められて、誰に対して力を持つのかが"
    "伝わる2〜3文の説明。渡した場所の産業・地形・人間関係のうち少なくとも"
    "一つを具体的に使う。「由緒ある」「謎めいた」のような、どの群にも"
    "当てはまる形容だけで済ませない), "
    "scale(この群の力がどこまで届くか。" + " / ".join(_SCALE_INFLUENCE) +
    " のいずれか一つ)の四つだけ。"
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "read": {"type": "string"},
        "text": {"type": "string"},
        "scale": {"type": "string", "enum": list(_SCALE_INFLUENCE)},
    },
    "required": ["name", "read", "text", "scale"],
    "additionalProperties": False,
}


def _should_roll(time: Stamp) -> bool:
    """月に一度、月初(1日)にだけロールする。"""
    return time.day == 1


def _characters_at(session: Session, place_id: int, time: Stamp) -> list:
    """その場所に居る、その時点で生きている人物。"""
    characters = session.scalars(
        world_createion_query.alive_characters_select(time)).all()
    resident_ids = set(session.scalars(
        common_query.resident_character_ids_select([place_id], time)).all())
    return [c for c in characters if c.id in resident_ids]


def _objects_at(session: Session, place_id: int, time: Stamp) -> list:
    """その場所に居る、その時点で残っている個体。"""
    objects = session.scalars(
        world_createion_query.alive_objects_select(time)).all()
    resident_ids = set(session.scalars(
        common_query.resident_object_ids_select([place_id], time)).all())
    return [o for o in objects if o.id in resident_ids]


def _place_context(place: Location) -> str:
    """個体の性格を考える材料になる、場所の `text` と参考カラム。"""
    lines = [place.text or "(説明なし)"]
    references = [
        label for label in (
            f"参考地域: {place.sample_region}" if place.sample_region else None,
            f"参考文化: {place.sample_culture}" if place.sample_culture else None,
            f"参考時代: {place.sample_era}" if place.sample_era else None,
        ) if label
    ]
    if references:
        lines.append(" / ".join(references))
    return "\n".join(lines)


def generate_random(session: Session, time: Stamp) -> Object | None:
    """ロールに当たったら、個体を一件 db へ確定して返す。当たらなければ None。"""
    if not _should_roll(time):
        return None

    seed = random.randrange(10 ** 9)
    rng = random.Random(seed)
    roll = rng.random()
    when = format_time(time)
    if roll >= PROBABILITY:
        print(f"[time_keepr/object] {when} 月初判定: "
              f"seed={seed} roll={roll:.4f} >= {PROBABILITY} → 見送り")
        return None
    print(f"[time_keepr/object] {when} 月初判定: "
          f"seed={seed} roll={roll:.4f} < {PROBABILITY} → 生成")

    places = session.scalars(
        world_createion_query.alive_locations_select(time)).all()
    # 人が居て、まだ個体の枠が空いていて、プロットのある場所だけを候補にする。
    eligible = [
        p for p in places
        if int(session.scalar(
            world_createion_query.character_count_at_place_select(p.id, time)) or 0) > 0
        and int(session.scalar(
            world_createion_query.object_count_at_place_select(p.id, time)) or 0)
        < world_createion_query.MAX_PER_LOCATION
        and world_createion_query.location_has_plot(session, p.id)
    ]
    if not eligible:
        print(f"[time_keepr/object] {when} 人が居て枠の空いている場所が無いため見送り")
        return None
    place = rng.choice(eligible)

    characters = _characters_at(session, place.id, time)
    objects = _objects_at(session, place.id, time)
    plots = story_createion_query.load_location_plot(session, place.id, time)

    draft = build_object()

    prompt = (
        f"場所: {place.name}({place.kind}) id={place.id}\n"
        f"場所の特徴:\n{_place_context(place)}\n"
        f"そこに居る人物(名前, 説明): "
        f"{[(c.name, c.text) for c in characters[:10]]}\n"
        f"既にある群(名前, 説明): {[(o.name, o.text) for o in objects[:10]] or '(無し)'}\n"
        f"この場所・時刻に関連する筋書き: {[p.text for p in plots] or '(指定なし)'}\n"
        f"現在の時刻: {time}\n"
        "この場所を拠り所に生まれる群を1件、決めてください。"
    )
    decided = ai_client.try_generate_json(prompt, _SCHEMA, system=_SYSTEM_PROMPT)

    draft["name"] = decided.get("name") or draft["name"]
    draft["read"] = decided.get("read") or draft["read"]
    draft["text"] = decided.get("text") or draft["text"]
    scale = decided.get("scale")
    if scale not in _SCALE_INFLUENCE:
        scale = _DEFAULT_SCALE
    draft["world_influence"] = _SCALE_INFLUENCE[scale]
    draft["start"] = time

    record = Object(**draft)
    session.add(record)
    session.flush()  # place から object_id で参照するため、先に id を確定する
    session.add(ObjectPlace(
        object_id=record.id, location_id=place.id,
        start=record.start, end=record.end))
    session.commit()
    print(f"[time_keepr/object] {when} 生成: {record.name}({record.read})"
          f" id={record.id} 拠り所={place.name}(id={place.id})"
          f" 規模={scale}(world_influence={record.world_influence})\n"
          f"    説明: {record.text or '(説明なし)'}")
    return record
