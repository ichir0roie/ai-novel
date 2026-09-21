#!/usr/bin/env python3
"""場所・時刻ごとに、その場に居合わせる人物・対象(`Character`。人物以外の国・組織なども含む)を巻き込んだ出来事を起こす。

出来事には `start`〜`end`(進行中と見なす幅)を持たせ、進行中の人物は次の出来事の対象にしない。
"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Mapping

from sqlalchemy import select

from DEM.ai_instructions.event_writing import (
    CHARACTER_NOTE_LIMIT, CHARACTER_NOTE_SEPARATOR,
    CHARACTER_TEXT_UPDATE_INSTRUCTION, EVENT_DURATION_INSTRUCTION,
    EVENT_PROGRESSION_INSTRUCTION, EVENT_RECORD_INSTRUCTION,
    RECENT_EVENT_LIMIT,
)
from DEM.ai_instructions.naming import PLACE_NAMING_INSTRUCTION
from DEM.ai_instructions.plot_writing import (
    CHARACTER_PLOT_INSTRUCTION, PLOT_PACING_INSTRUCTION, plot_span_instruction,
)
from DEM.ai_instructions.principles import AVOID_NARO_TEMPLATE_INSTRUCTION
from DEM.data_access_logic.query import (
    common_query, story_createion_query, world_createion_query,
)
from DEM.data_access_logic.query.base import location_active_condition
from DEM.db.schema import (
    Character, CharacterPlace, CharacterPlot, Event, EventCharacter,
    Location, Session, Stamp,
)
from DEM.local_ai import ai_client
from DEM.local_ai.time_keeper import constants
from DEM.local_ai.time_keeper._format import add_days, format_time
from DEM.randomizer.random_location_generator import build_location

_EVENT_TEXT_INSTRUCTION = (
    "選ばれた出来事の候補(name と summary)を、当事者ごとの思考・感情・"
    "望み・恐れ・行動を土台にして記録に起こす。候補の筋から外れない。"
    + EVENT_RECORD_INSTRUCTION
)


_PLOT_TEXT_INSTRUCTION = (
    "text はその人物の信念・思考の核になる情報として扱う。日常の細かな"
    "出来事では character_plots 自体を空リストのままにし、信念・立場が"
    "大きく動いたときだけ書く。書くときは一文で済ませず、"
    + CHARACTER_PLOT_INSTRUCTION
)

_INVOLVEMENT_INSTRUCTION = (
    "関わった人物・対象があれば、その id を渡した一覧の中からだけ選んで "
    "character_ids に入れる(複数可)。"
)

_CHARACTER_MOVE_INSTRUCTION = (
    "character_moves は、この出来事で居場所が変わった人物だけのリスト"
    "(旅立ち・移住・避難・帰還など)。各要素は character_id(渡した"
    "「居合わせる人物」の id)と location_id(渡した「移動先の候補」の id)の"
    "二つ。誰も動いていなければ空リストにする。"
)

_LOCATION_CHANGE_INSTRUCTION = (
    "この出来事が場所自身の改廃(消滅・新設)に及ぶときだけ、"
    "location_abolished / location_founded を埋める。何も変わっていなければ "
    "location_abolished は false、location_founded は null のままにする。"
    "location_founded の固有名詞は次の基準で名づける。"
    + PLACE_NAMING_INSTRUCTION
)

_JUDGEMENT_KEYS = ("thought", "emotion", "wish", "fear", "action")

_JUDGEMENT_SYSTEM_PROMPT = (
    "あなたは架空の世界観の中で、ある一人の人物、または人物以外の一つの対象"
    "(国・組織・集団・物)の立場に立って考える設定作家です。"
    "渡す場所・直近の出来事・筋書き・居合わせる相手を踏まえ、「この当事者」の"
    "いまを、その kind・text・口調・性格の数値・立場・世界線への影響度から推測して"
    "ください。人物なら性格と人間関係から、人物以外なら方針と力の及ぶ範囲から。"
    "他の当事者のことは決めない。この当事者自身のことだけを書く。"
    "JSON で答えてください。キーは thought(思考。いまの状況をどう受け止め、"
    "何を考えているか), emotion(感情。何に対して怒り・喜び・悲しみ・退屈・"
    "不安などを抱いているか。感情の名前を含める), wish(望み。何を手に入れ"
    "たい・何をしたいか), fear(恐れ。何を失いたくない・何が起きてほしく"
    "ないか), action(行動。この時点で実際に何をするか。話す・動く・作る・"
    "出かける・黙るなど具体的な動作で)の五つ。各1〜2文。"
)

_JUDGEMENT_SCHEMA = {
    "type": "object",
    "properties": {key: {"type": "string"} for key in _JUDGEMENT_KEYS},
    "required": list(_JUDGEMENT_KEYS),
    "additionalProperties": False,
}

_CANDIDATE_SYSTEM_PROMPT = (
    "あなたは架空の世界観の中で、ある場所に起こりうる出来事を列挙する"
    "設定作家です。渡す場所・居合わせる人物・対象・当事者ごとの思考・感情・"
    "望み・恐れ・行動・直近の出来事・筋書きを踏まえ、これらの行動が同じ場で"
    "重なった結果として、この時点で起こりうる出来事の候補を"
    f"{constants.CANDIDATE_COUNT}件挙げてください。"
    "どれが起きるかはあとでサイコロで決めるので、候補どうしは性質を"
    "ばらけさせる。日常の小さな出来事、感情がぶつかる出来事、偶発的な"
    "出来事(事故・天候・病・思いがけない出会い)、居場所が変わる出来事"
    "(旅立ち・帰還・避難)、笑いや祝いの出来事、取り決めや対立が動く出来事"
    "など、種類の違うものを混ぜ、交渉・要求・合意の型に寄せない。"
    "各候補は当事者の action と矛盾しない範囲で立てる。"
    + EVENT_PROGRESSION_INSTRUCTION + AVOID_NARO_TEMPLATE_INSTRUCTION +
    "JSON で答えてください。キーは candidates(候補のリスト。各要素は "
    "name(出来事の名前)と summary(何が起きて誰が関わるか。2〜3文)の二つ)だけ。"
)

_CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["name", "summary"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["candidates"],
    "additionalProperties": False,
}

_PLACE_SYSTEM_PROMPT = (
    "あなたは架空の世界観の中で、ある場所に起きたことを記録する設定作家です。"
    "その場所自身の情報、そこに居合わせる人物・対象の一覧、"
    "その場所の直近の出来事、当事者ごとの思考・感情・"
    "望み・恐れ・行動、そしてサイコロで選ばれた出来事の候補を渡すので、"
    "その候補をこの場所にこの時点で起きた出来事として1件、記録に起こして"
    "ください。候補の name は event_name にそのまま使うか、整えてもよい。"
    + _INVOLVEMENT_INSTRUCTION + _CHARACTER_MOVE_INSTRUCTION
    + AVOID_NARO_TEMPLATE_INSTRUCTION +
    "JSON で答えてください。キーは "
    "event_name(出来事の名前), event_text(出来事の内容。"
    + _EVENT_TEXT_INSTRUCTION + "), "
    "character_ids(関わった人物・対象の id のリスト。渡した「居合わせる人物・対象」の "
    "character_id からだけ選ぶ), "
    "character_moves(居場所が変わった人物のリスト。各要素は character_id と "
    "location_id), "
    "character_plots(関わった人物のうち、信念・立場が大きく動いた者だけの"
    "リスト。各要素は character_id(対象の人物 id), text("
    + _PLOT_TEXT_INSTRUCTION + ")の二つ), "
    "character_updates(関わった人物・対象のうち、この出来事でレコード自体が"
    "変わった者だけのリスト。各要素は character_id(対象の id)と、"
    + CHARACTER_TEXT_UPDATE_INSTRUCTION + "), "
    "location_abolished(bool。この出来事でこの場所自体が消滅・放棄されたか), "
    "location_founded(この出来事でこの場所の配下に新しい場所が生まれたなら "
    "{name, kind, text, environment}。無ければ null), "
    + _LOCATION_CHANGE_INSTRUCTION + EVENT_DURATION_INSTRUCTION
)

_LOCATION_FOUND_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "name": {"type": "string"},
        "kind": {"type": "string"},
        "text": {"type": "string"},
        "environment": {"type": "string"},
    },
    "required": ["name", "kind", "text", "environment"],
    "additionalProperties": False,
}

_PLACE_SCHEMA = {
    "type": "object",
    "properties": {
        "event_name": {"type": "string"},
        "event_text": {"type": "string"},
        "character_ids": {"type": "array", "items": {"type": "integer"}},
        "character_moves": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "character_id": {"type": "integer"},
                    "location_id": {"type": "integer"},
                },
                "required": ["character_id", "location_id"],
                "additionalProperties": False,
            },
        },
        "character_plots": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "character_id": {"type": "integer"},
                    "text": {"type": "string"},
                },
                "required": ["character_id", "text"],
                "additionalProperties": False,
            },
        },
        "character_updates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "character_id": {"type": "integer"},
                    "text": {"type": "string"},
                },
                "required": ["character_id"],
                "additionalProperties": False,
            },
        },
        "location_abolished": {"type": "boolean"},
        "location_founded": _LOCATION_FOUND_SCHEMA,
        "event_duration_days": {
            "type": "integer",
            "minimum": constants.EVENT_DURATION_RANGE_DAYS[0],
            "maximum": constants.EVENT_DURATION_RANGE_DAYS[1],
        },
    },
    "required": [
        "event_name", "event_text", "character_ids",
        "character_moves",
        "character_plots", "character_updates",
        "location_abolished", "location_founded",
        "event_duration_days",
    ],
    "additionalProperties": False,
}


def _should_roll(time: Stamp) -> bool:
    """月に一度、月初(1日)にだけロールする。"""
    return time.day == 1


def _append_note(record: Character, note: str) -> None:
    """人物の `text` に、生成時の基礎説明を残したまま直近の追記だけを積み足す(先頭の一段は常に残す)。"""
    if not record.text:
        record.text = note
        return
    base, *notes = record.text.split(CHARACTER_NOTE_SEPARATOR)
    notes.append(note)
    notes = notes[-(CHARACTER_NOTE_LIMIT - 1):] if CHARACTER_NOTE_LIMIT > 1 else []
    record.text = CHARACTER_NOTE_SEPARATOR.join([base, *notes])


def _current_place_id(session: Session, character: Character, time: Stamp) -> int | None:
    place = session.scalars(
        common_query.character_place_select(character.id, time)).first()
    return place.location_id if place else None


def _group_by_place(session: Session, time: Stamp) -> dict[int, list[Character]]:
    """その時点で生きている人物・対象を、いま居る場所ごとにまとめる。進行中の出来事に関わる者は外す。"""
    grouped: dict[int, list[Character]] = defaultdict(list)

    busy_character_ids = set(session.scalars(
        world_createion_query.busy_character_ids_select(time)).all())

    active_place_ids = set(session.scalars(
        select(Location.id).where(location_active_condition())).all())

    characters = session.scalars(
        world_createion_query.alive_characters_select(time)).all()
    for character in characters:
        if character.id in busy_character_ids:
            continue
        place_id = _current_place_id(session, character, time)
        if place_id is None or place_id not in active_place_ids:
            continue
        grouped[place_id].append(character)

    return grouped


_PLOT_COMPLETION_SYSTEM_PROMPT = (
    "あなたは物語の進行を見届ける編集者です。人物一人の筋書き(起・承・転・結)と、"
    "その人物が関わった直近の出来事、そしていま起きたばかりの出来事を渡します。"
    "いま起きた出来事によって、筋書きの「結」に相当する到達点まで至ったかどうかを"
    "判定してください。転機(転)を迎えただけ、結へ向かう途中、という段階では"
    "完了と見なさない。結に書かれた行き着き先(成功・失敗・変質など)が、"
    "出来事の記録として実際に起きたときだけ完了とする。"
    "筋書きには期間(start〜end)があり、end が結に至る予定の時点。現在の時刻が"
    "期間の終わりにまだ遠いうちは、結に似た出来事が起きても通過点と見なして"
    "完了としない。"
    "JSON で答えてください。キーは completed(bool)と reason(一〜二文の根拠)の二つ。"
)

_PLOT_COMPLETION_SCHEMA = {
    "type": "object",
    "properties": {
        "completed": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["completed", "reason"],
    "additionalProperties": False,
}


def _plot_span_label(plot: CharacterPlot) -> str:
    start = format_time(plot.start) if plot.start else "不明"
    end = format_time(plot.end) if plot.end else "未定"
    return f"{start}〜{end}"


def _judge_plot_completed(
    session: Session, plot: CharacterPlot, character: Character,
    event: Event, time: Stamp,
) -> bool:
    recent = session.scalars(
        common_query.events_of_select(character.id, until=time, limit=RECENT_EVENT_LIMIT)
    ).all()
    prompt = (
        f"人物: {character.name}\n"
        f"人物の説明: {character.text}\n"
        f"筋書き:\n{plot.text}\n"
        f"筋書きの期間: {_plot_span_label(plot)}\n"
        f"現在の時刻: {format_time(time)}\n"
        f"この人物が関わった直近の出来事(名前): {[e.name for e in recent]}\n"
        f"いま起きた出来事: {event.name}\n{event.text}\n"
        "この出来事で筋書きは完了したか判定してください。"
    )
    decided = ai_client.try_generate_json(
        prompt, _PLOT_COMPLETION_SCHEMA, system=_PLOT_COMPLETION_SYSTEM_PROMPT)
    return bool(decided.get("completed"))


def _character_recent_event_names(
    session: Session, character_id: int, time: Stamp,
) -> list[str]:
    """その人物・対象自身が、場所を問わず関わった直近の出来事の名前。"""
    events = session.scalars(
        common_query.events_of_select(character_id, until=time, limit=RECENT_EVENT_LIMIT)
    ).all()
    return [e.name for e in events]


def _plot_recent_event_names(
    session: Session, top_location_id: int | None, place_id: int, time: Stamp,
) -> list[str]:
    """その場所と、そこから筋書きの掛かる最上位の場所 `top_location_id` までの上位の場所で直近使われた出来事の名前。

    横(兄弟の場所)の出来事は含めない。筋書きの配下全体を渡すと、他の国の
    展開まで持ち込まれて場所ごとの差が消えるため(2026-09 に観測)。
    """
    place_ids = []
    for step in reversed(common_query.place_path(session, place_id)):
        place_ids.append(step["id"])
        if step["id"] == top_location_id:
            break
    events = session.scalars(
        common_query.events_in_locations_select(
            place_ids, until=time, limit=RECENT_EVENT_LIMIT)
    ).all()
    return [e.name for e in events]


def _think_participants(
    situation: str, characters_payload: list[dict],
) -> list[dict]:
    """当事者ごとに思考・感情・望み・恐れ・行動を推測させる。出来事の候補はこれを土台に立てる。"""
    judgements: list[dict] = []
    for payload in characters_payload:
        prompt = (
            f"この当事者({payload['kind']}): {payload}\n"
            f"{situation}"
            "この当事者のいまの思考・感情・望み・恐れ・行動を推測してください。"
        )
        decided = ai_client.try_generate_json(
            prompt, _JUDGEMENT_SCHEMA, system=_JUDGEMENT_SYSTEM_PROMPT)
        fields = {key: (decided.get(key) or "").strip() for key in _JUDGEMENT_KEYS}
        if not fields["action"]:
            continue
        judgements.append({"character_id": payload["character_id"], "name": payload["name"], **fields})
    return judgements


def _roll_candidate(
    rng: random.Random, situation: str, judgements: list[dict],
) -> dict | None:
    """起こりうる出来事の候補をローカル AI に列挙させ、その中から一件をサイコロで選ぶ。"""
    prompt = (
        f"当事者ごとの思考・感情・望み・恐れ・行動: {judgements or '(無し)'}\n"
        f"{situation}"
        f"この場所にこの時点で起こりうる出来事の候補を{constants.CANDIDATE_COUNT}件挙げてください。"
    )
    decided = ai_client.try_generate_json(
        prompt, _CANDIDATE_SCHEMA, system=_CANDIDATE_SYSTEM_PROMPT)
    candidates = [
        c for c in (decided.get("candidates") or [])
        if isinstance(c, dict) and c.get("name")
    ]
    if not candidates:
        return None
    chosen = rng.choice(candidates)
    return {"name": chosen["name"], "summary": chosen.get("summary") or "",
            "rolled": f"{candidates.index(chosen) + 1}/{len(candidates)}"}


def _move_destinations(
    session: Session, place_id: int, time: Stamp,
) -> list[dict]:
    """人物が移れる先。一つ上の圏内にある、いま存在する場所。"""
    root_id = common_query.place_up(session, place_id, constants.REACH_LEVELS)
    nearby_ids = set(common_query.descendant_place_ids(session, root_id))
    nearby_ids -= {place_id, root_id}
    places = session.scalars(
        world_createion_query.alive_locations_select(time)
        .where(Location.id.in_(nearby_ids), location_active_condition())
    ).all()
    return [{"location_id": p.id, "name": p.name, "kind": p.kind}
            for p in places[:constants.MOVE_DESTINATION_LIMIT]]


def _progress_place(
    session: Session, place_id: int,
    characters: list[Character], time: Stamp, rng: random.Random,
) -> Event | None:
    recent_events = session.scalars(
        common_query.events_of_select(place_id, until=time, limit=RECENT_EVENT_LIMIT)
    ).all()
    place = session.get(Location, place_id)
    plots = story_createion_query.load_location_plot(session, place_id, time)
    plot_text = story_createion_query.join_plot_text(plots)
    plot_recent_events = (
        _plot_recent_event_names(session, plots[0].location_id, place_id, time)
        if plots else []
    )
    character_plots = {
        c.id: story_createion_query.load_character_plot(session, c.id, time)
        for c in characters[:20]
    }
    characters_payload = [
        {"character_id": c.id, "kind": c.kind, "name": c.name, "tone": c.tone, "text": c.text,
         "traits": {column: getattr(c, column) for column in constants.TRAIT_COLUMNS},
         "world_influence": c.world_influence,
         "plot": [{"text": p.text, "span": _plot_span_label(p)}
                  for p in character_plots.get(c.id, [])] or "(指定なし)",
         "recent_events": _character_recent_event_names(session, c.id, time)}
        for c in characters[:20]
    ]
    destinations = _move_destinations(session, place_id, time)
    plot_years = rng.randint(*constants.CHARACTER_PLOT_YEARS_RANGE)

    situation = (
        f"場所id: {place_id}\n"
        f"場所の情報: {(place.name, place.kind, place.text) if place else None}\n"
        f"居合わせる人物・対象(kind が「人物」以外なら国・組織・集団・物。"
        f"recent_events はその者自身が場所を問わず関わった直近の出来事): "
        f"{characters_payload}\n"
        f"直近の出来事(名前): {[e.name for e in recent_events]}\n"
        f"進めたい筋書き(上位の場所のものから順につなげた本文):\n{plot_text or '(指定なし)'}\n"
        f"筋書きに関わる直近の出来事(この場所とその上位の場所で直近使われた出来事の名前): "
        f"{plot_recent_events or '(無し)'}\n"
        f"現在の時刻: {time}\n"
        + (PLOT_PACING_INSTRUCTION + "\n" if any(character_plots.values()) else "")
    )
    judgements = _think_participants(situation, characters_payload)
    candidate = _roll_candidate(rng, situation, judgements)
    if candidate is None:
        return None

    prompt = (
        situation
        + f"移動先の候補(character_moves の location_id はここからだけ選ぶ): "
        f"{destinations or '(無し)'}\n"
        f"当事者ごとの思考・感情・望み・恐れ・行動(先に推測したもの): "
        f"{judgements or '(無し)'}\n"
        f"サイコロで選ばれた出来事の候補: "
        f"{ {'name': candidate['name'], 'summary': candidate['summary']} }\n"
        "この候補を、この場所にこの時点で起きた出来事として記録してください。"
        "event_text 内では番号ではなく名前で書く。"
        + ("進めたい筋書きがあるなら、そこへ向かう一歩になる出来事を優先する。"
           if plots else "")
        + ("居合わせる人物・対象のうち plot を持つ者がいれば、その者個人について"
           "進めたい筋書きとして扱い、そこへ向かう一歩になる出来事を優先する。"
           if any(character_plots.values()) else "")
        + "character_plots に新しく書く筋書きについて: " + plot_span_instruction(plot_years)
    )
    decided = ai_client.try_generate_json(prompt, _PLACE_SCHEMA, system=_PLACE_SYSTEM_PROMPT)

    if not decided.get("event_name"):
        return None

    event_name = decided["event_name"]
    event_text = decided.get("event_text") or ""

    character_ids = {c.id: c for c in characters}

    def _valid_ids(raw, pool: Mapping[int, object]) -> list[int]:
        result: list[int] = []
        for value in raw or []:
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            if value in pool and value not in result:
                result.append(value)
        return result

    involved_character_ids = _valid_ids(decided.get("character_ids"), character_ids)

    destination_names = {d["location_id"]: d["name"] for d in destinations}
    move_notes = []
    for move in decided.get("character_moves") or []:
        if not isinstance(move, dict):
            continue
        try:
            character_id = int(move.get("character_id") or 0)
            location_id = int(move.get("location_id") or 0)
        except (TypeError, ValueError):
            continue
        character = character_ids.get(character_id)
        if character is None or location_id not in destination_names:
            continue
        for current in session.scalars(
                common_query.character_place_select(character_id, time)).all():
            current.end = time
        session.add(CharacterPlace(
            character_id=character_id, location_id=location_id,
            start=time, end=character.end))
        if character_id not in involved_character_ids:
            involved_character_ids.append(character_id)
        move_notes.append(f"{character.name} → {destination_names[location_id]}")

    try:
        duration_days = int(decided.get("event_duration_days"))
    except (TypeError, ValueError):
        duration_days = constants.DEFAULT_EVENT_DURATION_DAYS
    duration_days = min(max(duration_days, constants.EVENT_DURATION_RANGE_DAYS[0]),
                        constants.EVENT_DURATION_RANGE_DAYS[1])
    end = add_days(time, duration_days)

    record = Event(
        name=event_name,
        text=event_text,
        time=time,
        location_id=place_id,
        start=time,
        end=end,
    )
    record.event_characters = [
        EventCharacter(character_id=cid) for cid in involved_character_ids
    ]
    session.add(record)

    plot_done_notes = []
    for cid in involved_character_ids:
        for plot in character_plots.get(cid, []):
            if plot.end is not None:
                continue
            if _judge_plot_completed(session, plot, character_ids[cid], record, time):
                plot.end = record.time
                plot_done_notes.append(f"{character_ids[cid].name}: id={plot.id} 完了")

    plot_notes = []
    for item in decided.get("character_plots") or []:
        if not isinstance(item, dict):
            continue
        try:
            character_id = int(item.get("character_id") or 0)
        except (TypeError, ValueError):
            continue
        text = item.get("text")
        if character_id not in character_ids or not text:
            continue
        plot_end = Stamp(time.year + plot_years, time.month, time.day)
        session.add(CharacterPlot(character_id=character_id, text=text, start=time, end=plot_end))
        plot_notes.append(f"{character_ids[character_id].name}({plot_years}年、〜{format_time(plot_end)}): {text}")

    update_notes = []
    for update in decided.get("character_updates") or []:
        if not isinstance(update, dict):
            continue
        try:
            character_id = int(update.get("character_id") or 0)
        except (TypeError, ValueError):
            continue
        character = character_ids.get(character_id)
        if character is None:
            continue
        applied = []
        if update.get("text"):
            _append_note(character, update["text"])
            applied.append(f"text+={update['text']}")
        if applied:
            update_notes.append(f"{character.name}: {', '.join(applied)}")

    location_notes = []
    if decided.get("location_abolished") and place is not None and place.end is None:
        place.end = time
        location_notes.append(f"{place.name}(id={place_id}): 消滅")

    founded = decided.get("location_founded")
    if isinstance(founded, dict) and founded.get("name"):
        draft = build_location(
            parent_id=place_id,
            name=founded.get("name"),
            kind=founded.get("kind") or "集落",
            text=founded.get("text") or "",
            environment=founded.get("environment") or (place.environment if place else None),
            start=time,
            active_random_generation=place.active_random_generation if place else False,
        )
        new_location = Location(**draft)
        session.add(new_location)
        session.flush()
        location_notes.append(f"{new_location.name}(id={new_location.id}): 新設")

    session.commit()
    when = format_time(time)
    involved_names = [
        name for name in (character_ids[cid].name for cid in involved_character_ids) if name
    ]
    print(f"[time_keepr/event] {when} 場所id={place_id}: "
          f"{record.name} {record.text}"
          f" / 継続: {duration_days}日({when}〜{format_time(end)})"
          + (f" / 関わった: {', '.join(involved_names)}" if involved_names else "")
          + f" / 候補 {candidate['rolled']}: {candidate['name']}"
          + (f" / 移動: {'; '.join(move_notes)}" if move_notes else "")
          + (f" / 筋書き完了: {'; '.join(plot_done_notes)}" if plot_done_notes else "")
          + (f" / 人物の筋書き: {'; '.join(plot_notes)}" if plot_notes else "")
          + (f" / 人物・対象更新: {'; '.join(update_notes)}" if update_notes else "")
          + (f" / 場所: {'; '.join(location_notes)}" if location_notes else ""))
    return record


def generate_random(session: Session, time: Stamp) -> list[Event]:
    """月初に、人物・対象が居る場所それぞれについて出来事を進行させる。"""
    if not _should_roll(time):
        return []

    seed = random.randrange(10 ** 9)
    rng = random.Random(seed)
    created: list[Event] = []

    grouped = _group_by_place(session, time)
    total_places = len(grouped)
    for i, (place_id, characters) in enumerate(grouped.items(), start=1):
        print(f"[time_keepr/event] 場所 {i}/{total_places} id={place_id}: "
              f"人物・対象{len(characters)}件")
        if rng.random() < constants.PLACE_PROBABILITY:
            event = _progress_place(session, place_id, characters, time, rng)
            if event is not None:
                created.append(event)

    return created
