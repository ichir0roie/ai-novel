#!/usr/bin/env python3
"""場所・時刻ごとに、その場に居合わせる人物・個体(`Object` も含む)を巻き込んだ出来事を起こす。

出来事には `start`〜`end`(進行中と見なす幅)を持たせ、進行中の人物は次の出来事の対象にしない。
候補は居合わせるものに加え、一つ上の圏内の個体(`_reach_objects`)や、新規に誕生する個体も含める。
"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Mapping

from sqlalchemy import select

from IHG.ai_instructions.event_writing import (
    CHARACTER_NOTE_LIMIT, CHARACTER_NOTE_SEPARATOR,
    CHARACTER_TEXT_UPDATE_INSTRUCTION, EVENT_DURATION_INSTRUCTION,
    EVENT_PROGRESSION_INSTRUCTION, EVENT_RECORD_INSTRUCTION,
    EVENT_RELATION_INSTRUCTION, OBJECT_ACTION_INSTRUCTION,
    OBJECT_TEXT_UPDATE_INSTRUCTION, RECENT_EVENT_LIMIT,
)
from IHG.ai_instructions.naming import PLACE_NAMING_INSTRUCTION, TERM_NAMING_INSTRUCTION
from IHG.ai_instructions.principles import AVOID_NARO_TEMPLATE_INSTRUCTION
from DEM.data_access_logic.query import (
    common_query, story_createion_query, world_createion_query,
)
from DEM.db.schema import (
    Character, CharacterDrive, Event, EventCharacter,
    EventObject, Location, Object, ObjectPlace, Session, Stamp,
)
from DEM.local_ai import ai_client
from DEM.local_ai.time_keeper._format import add_days, format_time
from DEM.local_ai.time_keeper.random_object_generator import (
    _DEFAULT_SCALE, _SCALE_INFLUENCE,
)
from DEM.randomizer.random_location_generator import build_location
from DEM.randomizer.random_object_generator import build_object

PLACE_PROBABILITY = 0.30  # 月初のロールのたび、場所1件につき30%の確率で出来事を起こす(場所ごとに数ヶ月に一度)

# 遠隔候補(`_reach_objects`)をどこまで拾うか。`read_cast` の既定
# (levels=1、「隣の集落にいる者も枠に入れる」)と同じ考え方をそろえる。
_REACH_LEVELS = 1
_REACH_OBJECT_LIMIT = 10

# event_duration_days の取りうる範囲。範囲外の値は丸める。
_EVENT_DURATION_RANGE_DAYS = (1, 90)
_DEFAULT_EVENT_DURATION_DAYS = 1

_EVENT_TEXT_INSTRUCTION = (
    "直近のeventのリストから、状況を把握する。年齢、性別、性格、emotion、"
    "textをベースに人物像を推測し、個体(国・組織・集団・物)はその text と"
    "世界線への影響度からいまの立場・方針を推測する。状況と、そこに居合わせる"
    "もの同士の関係に基づいて、人物と個体それぞれの行動を決定する。人物も"
    "個体も、自分や他の人物・個体・場所に影響を与える。"
    + EVENT_PROGRESSION_INSTRUCTION + EVENT_RECORD_INSTRUCTION
)


_DRIVE_TEXT_INSTRUCTION = (
    "text はその人物の信念・思考の核になる情報として扱う。"
    "出来事なら character_drives 自体を空リストのままにする。"
)

_INVOLVEMENT_INSTRUCTION = (
    EVENT_RELATION_INSTRUCTION + OBJECT_ACTION_INSTRUCTION +
    "関わった人物・個体があれば、その id を渡した一覧の中からだけ選んで "
    "character_ids / object_ids に入れる(複数可)。object_ids には、"
    "居合わせる個体だけでなく「一つ上の圏内の個体」の中から遠隔で"
    "働きかけてきた候補を選んでもよい。居合わせる個体があるのに "
    "object_ids が空になるのは、その個体が本当に何一つ関わらなかったときだけ。"
)

_OBJECT_FOUND_INSTRUCTION = (
    "居合わせる個体にも一つ上の圏内の候補にも、この出来事を起こすのに"
    "ふさわしい主体が見当たらないときに限り、object_founded を埋めて"
    "新しい個体(国・組織・商会・氏族・徒党など)をこの出来事の中で誕生"
    "させてよい。埋めるなら {name, read, text, scale}(name は固有名詞、"
    "read は読み、text はこの個体が何であって、何を決められて誰に対して"
    "力を持つのかが伝わる説明、scale はこの個体の力がどこまで届くか。"
    + " / ".join(_SCALE_INFLUENCE) + " のいずれか一つ)。既にある個体・"
    "候補で足りるなら object_founded は null のままにする。"
    + TERM_NAMING_INSTRUCTION
)

_CHARACTER_UPDATE_INSTRUCTION = (
    CHARACTER_TEXT_UPDATE_INSTRUCTION + "belong_id はその人物の"
    "所属がこの出来事で変わったときだけ、渡した「居合わせる個体」の id から"
    "選ぶ(変わっていなければキー自体を省く)。"
)

_LOCATION_CHANGE_INSTRUCTION = (
    "この出来事が場所自身の改廃(消滅・新設)に及ぶときだけ、"
    "location_abolished / location_founded を埋める。何も変わっていなければ "
    "location_abolished は false、location_founded は null のままにする。"
    "location_founded の固有名詞は次の基準で名づける。"
    + PLACE_NAMING_INSTRUCTION
)

_TYPO_CHECK_SYSTEM_PROMPT = (
    "あなたは、生成された出来事の記録を確認する校正者です。渡す「正しい"
    "名前の一覧」(人物は character_id、個体は object_id を持つ)と、"
    "出来事の名前・本文を見比べ、本文中に一覧の名前と紛らわしい誤字・"
    "表記ゆれ(似ているが違う表記、文字の入れ替わり、送り仮名や括弧の"
    "崩れなど)が無いかを確認してください。見つかったら、一覧にある"
    "正式な表記に直してください。誤字が無ければ、名前も本文もそのまま"
    "返す。名前の表記以外(出来事の展開や意味、文体)は書き換えない。"
    "JSON で答えてください。キーは event_name(直した出来事の名前)、"
    "event_text(直した出来事の本文)の二つだけ。"
)


def _check_typos(
    event_name: str, event_text: str,
    characters: list[Character], objects: list[Object], reach_objects: list[Object],
) -> tuple[str, str]:
    """生成した出来事の名前・本文を、渡した人物・個体の正式名と照らして誤字・表記ゆれが無いか、もう一度ローカルAIに確認させる。"""
    known_names = (
        [{"character_id": c.id, "name": c.name} for c in characters]
        + [{"object_id": o.id, "name": o.name} for o in objects]
        + [{"object_id": o.id, "name": o.name} for o in reach_objects]
    )
    if not known_names:
        return event_name, event_text
    prompt = (
        f"正しい名前の一覧: {known_names}\n"
        f"出来事の名前: {event_name}\n"
        f"出来事の本文: {event_text}\n"
        "誤字・表記ゆれが無いか確認し、あれば直してください。"
    )
    checked = ai_client.try_generate_json(prompt, system=_TYPO_CHECK_SYSTEM_PROMPT)
    return (
        checked.get("event_name") or event_name,
        checked.get("event_text") or event_text,
    )


_PLACE_SYSTEM_PROMPT = (
    "あなたは架空の世界観の中で、ある場所に起きたことを記録する設定作家です。"
    "その場所自身の情報、そこに居合わせる人物・個体の一覧、一つ上の圏内で"
    "拠点を持つ個体の候補、その場所の直近の出来事を渡すので、この時点で"
    "この場所に起きる出来事を1件だけ考えてください。"
    + _INVOLVEMENT_INSTRUCTION + AVOID_NARO_TEMPLATE_INSTRUCTION +
    "JSON で答えてください。キーは "
    "event_name(出来事の名前), event_text(出来事の内容。"
    + _EVENT_TEXT_INSTRUCTION + "), "
    "character_ids(関わった人物の id のリスト。渡した「居合わせる人物」の "
    "character_id からだけ選ぶ), object_ids(関わった個体の id のリスト。渡した"
    "「居合わせる個体」と「一つ上の圏内の個体」の object_id からだけ選ぶ), "
    "character_drives(関わった人物のうち、情動・欲求が動いた者だけのリスト。"
    "各要素は character_id(対象の人物 id), text(" + _DRIVE_TEXT_INSTRUCTION +
    "), level(その情動の強さ。1〜10の整数)の三つ), "
    "character_updates(関わった人物のうち、この出来事で人物レコード自体が"
    "変わった者だけのリスト。各要素は character_id(対象の人物 id)と、"
    + _CHARACTER_UPDATE_INSTRUCTION + "), "
    "object_updates(関わった個体のうち、この出来事で個体レコード自体が"
    "変わったものだけのリスト。各要素は object_id(対象の個体 id)と、"
    + OBJECT_TEXT_UPDATE_INSTRUCTION + "), "
    "object_founded(" + _OBJECT_FOUND_INSTRUCTION + "。無ければ null), "
    "location_abolished(bool。この出来事でこの場所自体が消滅・放棄されたか), "
    "location_founded(この出来事でこの場所の配下に新しい場所が生まれたなら "
    "{name, kind, text, environment}。無ければ null), "
    + _LOCATION_CHANGE_INSTRUCTION + EVENT_DURATION_INSTRUCTION
)


def _should_roll(time: Stamp) -> bool:
    """月に一度、月初(1日)にだけロールする。"""
    return time.day == 1


def _append_note(record: Character | Object, note: str) -> None:
    """人物・個体の `text` に、生成時の基礎説明を残したまま直近の追記だけを積み足す(先頭の一段は常に残す)。"""
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


def _current_object_place_id(session: Session, obj: Object, time: Stamp) -> int | None:
    place = session.scalars(
        common_query.object_place_select(obj.id, time)).first()
    return place.location_id if place else None


def _group_by_place(
    session: Session, time: Stamp,
) -> dict[int, tuple[list[Character], list[Object]]]:
    """その時点で生きている人物・個体を、いま居る場所ごとにまとめる。進行中の出来事に関わる人物は外す。"""
    grouped: dict[int, tuple[list[Character], list[Object]]] = defaultdict(
        lambda: ([], []))

    busy_character_ids = set(session.scalars(
        world_createion_query.busy_character_ids_select(time)).all())

    characters = session.scalars(
        world_createion_query.alive_characters_select(time)).all()
    for character in characters:
        if character.id in busy_character_ids:
            continue
        place_id = _current_place_id(session, character, time)
        if place_id is None:
            continue
        grouped[place_id][0].append(character)

    objects = session.scalars(
        world_createion_query.alive_objects_select(time)).all()
    for obj in objects:
        place_id = _current_object_place_id(session, obj, time)
        if place_id is None:
            continue
        grouped[place_id][1].append(obj)

    return grouped


def _reach_objects(
    session: Session,
    grouped: dict[int, tuple[list[Character], list[Object]]],
    place_id: int,
    exclude_ids: set[int],
) -> list[Object]:
    """その場に今いなくても、一つ上の圏内から遠隔で出来事に関与できる個体の候補。追加の select は要らない。"""
    root_id = common_query.place_up(session, place_id, _REACH_LEVELS)
    nearby_ids = common_query.descendant_place_ids(session, root_id)
    found: list[Object] = []
    seen = set(exclude_ids)
    for nearby_id in nearby_ids:
        if nearby_id == place_id:
            continue
        for obj in grouped.get(nearby_id, ([], []))[1]:
            if obj.id in seen:
                continue
            seen.add(obj.id)
            found.append(obj)
            if len(found) >= _REACH_OBJECT_LIMIT:
                return found
    return found


def _progress_place(
    session: Session, place_id: int,
    characters: list[Character], objects: list[Object],
    reach_objects: list[Object], time: Stamp,
) -> Event | None:
    recent_events = session.scalars(
        common_query.events_of_select(place_id, until=time, limit=RECENT_EVENT_LIMIT)
    ).all()
    place = session.get(Location, place_id)
    plots = story_createion_query.load_location_plot(session, place_id, time)
    character_plots = {
        c.id: [p.text for p in story_createion_query.load_character_plot(session, c.id, time)]
        for c in characters[:20]
    }
    characters_payload = [
        {"character_id": c.id, "name": c.name, "tone": c.tone, "text": c.text,
         "plot": character_plots.get(c.id) or "(指定なし)"}
        for c in characters[:20]
    ]

    prompt = (
        f"場所id: {place_id}\n"
        f"場所の情報: {(place.name, place.kind, place.text) if place else None}\n"
        f"居合わせる人物: {characters_payload}\n"
        f"居合わせる個体(国・組織・集団・物): "
        f"{[{'object_id': o.id, 'name': o.name, 'text': o.text, 'world_influence': o.world_influence} for o in objects[:20]]}\n"
        f"一つ上の圏内で拠点を持つ個体(今はここに居ないが、遠隔で"
        f"働きかけてくる余地がある候補): "
        f"{[{'object_id': o.id, 'name': o.name, 'text': o.text, 'world_influence': o.world_influence} for o in reach_objects] or '(無し)'}\n"
        f"直近の出来事(名前): {[e.name for e in recent_events]}\n"
        f"進めたい筋書き: {[p.text for p in plots] or '(指定なし)'}\n"
        f"現在の時刻: {time}\n"
        "この場所に、この時点で起きる出来事を1件、決めてください。"
        "居合わせる人物・個体・場所のうち、どれとどれが噛み合って"
        "この出来事になったのかを踏まえる。人物の character_id と個体の "
        "object_id は別々の番号空間なので、event_text 内で番号に触れるなら "
        "「character_id」「object_id」のどちらの番号かが分かる書き方にする"
        "(迷うなら番号ではなく名前だけで書く)。"
        + ("進めたい筋書きがあるなら、そこへ向かう一歩になる出来事を優先する。"
           if plots else "")
        + ("居合わせる人物のうち plot を持つ者がいれば、その人物個人について"
           "進めたい筋書きとして扱い、そこへ向かう一歩になる出来事を優先する。"
           if any(character_plots.values()) else "")
    )
    decided = ai_client.try_generate_json(prompt, system=_PLACE_SYSTEM_PROMPT)

    if not decided.get("event_name"):
        return None

    event_name, event_text = _check_typos(
        decided["event_name"], decided.get("event_text") or "",
        characters, objects, reach_objects,
    )

    character_ids = {c.id: c for c in characters}
    object_ids = {o.id: o for o in objects}
    object_ids.update({o.id: o for o in reach_objects})

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
    involved_object_ids = _valid_ids(decided.get("object_ids"), object_ids)

    object_found_notes = []
    # 噛み合う主体が無いとき、ローカル AI がこの出来事の中で新しい個体を誕生
    # させてよい。プロットの無い場所には生まない。
    founded_object = decided.get("object_founded")
    if isinstance(founded_object, dict) and founded_object.get("name") and plots:
        scale = founded_object.get("scale")
        if scale not in _SCALE_INFLUENCE:
            scale = _DEFAULT_SCALE
        draft = build_object()
        draft["name"] = founded_object.get("name") or draft["name"]
        draft["read"] = founded_object.get("read") or draft["read"]
        draft["text"] = founded_object.get("text") or draft["text"]
        draft["world_influence"] = _SCALE_INFLUENCE[scale]
        draft["start"] = time
        new_object = Object(**draft)
        session.add(new_object)
        session.flush()
        session.add(ObjectPlace(
            object_id=new_object.id, location_id=place_id,
            start=new_object.start, end=new_object.end))
        object_ids[new_object.id] = new_object
        involved_object_ids.append(new_object.id)
        object_found_notes.append(
            f"{new_object.name}(id={new_object.id}, 規模={scale}): 新規誕生")

    try:
        duration_days = int(decided.get("event_duration_days"))
    except (TypeError, ValueError):
        duration_days = _DEFAULT_EVENT_DURATION_DAYS
    duration_days = min(max(duration_days, _EVENT_DURATION_RANGE_DAYS[0]),
                         _EVENT_DURATION_RANGE_DAYS[1])
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
    record.event_objects = [
        EventObject(object_id=oid) for oid in involved_object_ids
    ]
    session.add(record)

    drive_notes = []
    for drive in decided.get("character_drives") or []:
        if not isinstance(drive, dict):
            continue
        try:
            character_id = int(drive.get("character_id") or 0)
        except (TypeError, ValueError):
            continue
        text = drive.get("text")
        if character_id not in character_ids or not text:
            continue
        level = int(drive.get("level") or 1)
        # 同じ人物に既に動いている情動(end が無いもの)があれば、
        # 積み増さずにその一件を更新する。
        existing_drive = session.scalar(
            select(CharacterDrive).where(
                CharacterDrive.character_id == character_id,
                CharacterDrive.end.is_(None),
            )
        )
        if existing_drive is not None:
            existing_drive.text = text
            existing_drive.level = level
        else:
            session.add(CharacterDrive(
                character_id=character_id, text=text,
                level=level, start=time, end=None,
            ))
        drive_notes.append(f"{character_ids[character_id].name}: {text}")

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
        if update.get("belong_id") is not None:
            try:
                belong_id = int(update["belong_id"])
            except (TypeError, ValueError):
                belong_id = None
            if belong_id in object_ids:
                character.belong_id = belong_id
                applied.append(f"belong_id={belong_id}")
        if applied:
            update_notes.append(f"{character.name}: {', '.join(applied)}")

    for update in decided.get("object_updates") or []:
        if not isinstance(update, dict):
            continue
        try:
            object_id = int(update.get("object_id") or 0)
        except (TypeError, ValueError):
            continue
        obj = object_ids.get(object_id)
        if obj is None or not update.get("text"):
            continue
        _append_note(obj, update["text"])
        update_notes.append(f"{obj.name}: text+={update['text']}")

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
        )
        new_location = Location(**draft)
        session.add(new_location)
        session.flush()
        location_notes.append(f"{new_location.name}(id={new_location.id}): 新設")

    session.commit()
    when = format_time(time)
    involved_names = [
        name for name in (
            [character_ids[cid].name for cid in involved_character_ids]
            + [object_ids[oid].name for oid in involved_object_ids]
        ) if name
    ]
    print(f"[time_keepr/event] {when} 場所id={place_id}: "
          f"{record.name} {record.text}"
          f" / 継続: {duration_days}日({when}〜{format_time(end)})"
          + (f" / 関わった: {', '.join(involved_names)}" if involved_names else "")
          + (f" / 情動: {'; '.join(drive_notes)}" if drive_notes else "")
          + (f" / 人物・個体更新: {'; '.join(update_notes)}" if update_notes else "")
          + (f" / 新規個体: {'; '.join(object_found_notes)}" if object_found_notes else "")
          + (f" / 場所: {'; '.join(location_notes)}" if location_notes else ""))
    return record


def generate_random(session: Session, time: Stamp) -> list[Event]:
    """月初に、人物・個体が居る場所それぞれについて出来事を進行させる。"""
    if not _should_roll(time):
        return []

    seed = random.randrange(10 ** 9)
    rng = random.Random(seed)
    created: list[Event] = []

    grouped = _group_by_place(session, time)
    total_places = len(grouped)
    for i, (place_id, (characters, objects)) in enumerate(grouped.items(), start=1):
        print(f"[time_keepr/event] 場所 {i}/{total_places} id={place_id}: "
              f"人物{len(characters)}人 個体{len(objects)}件")
        if rng.random() < PLACE_PROBABILITY:
            reach_objects = _reach_objects(
                session, grouped, place_id, {o.id for o in objects})
            event = _progress_place(
                session, place_id, characters, objects, reach_objects, time)
            if event is not None:
                created.append(event)

    return created
