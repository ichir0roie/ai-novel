#!/usr/bin/env python3
"""**場所・時刻ごとに、その場に居合わせる人物・個体を巻き込んだ出来事を起こす。**"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Mapping

from sqlalchemy import select

from DEM.ai_instructions.event_writing import (
    CHARACTER_NOTE_LIMIT, CHARACTER_NOTE_SEPARATOR,
    CHARACTER_TEXT_UPDATE_INSTRUCTION, EVENT_PROGRESSION_INSTRUCTION,
    EVENT_SCENE_INSTRUCTION, RECENT_EVENT_LIMIT,
)
from DEM.ai_instructions.naming import PLACE_NAMING_INSTRUCTION
from DEM.ai_instructions.principles import AVOID_NARO_TEMPLATE_INSTRUCTION
from DEM.data_access_logic.query import (
    common_query, story_createion_query, world_createion_query,
)
from DEM.db.schema import (
    Character, CharacterDrive, Event, EventCharacter,
    EventObject, Location, LocationResource, Object, Session, Stamp,
)
from DEM.local_ai import ai_client
from DEM.local_ai.time_keeper import random_location_resource_generator
from DEM.local_ai.time_keeper._format import format_time
from DEM.randomizer.random_location_generator import build_location
from DEM.randomizer.random_location_resource_generator import (
    build_location_resource,
)

EVENT_ROLL_INTERVAL_DAYS = 3  # 3日毎に、人物・個体が居る場所それぞれでロールする
PLACE_PROBABILITY = 0.10  # ロールのたび、場所1件につき10%の確率で出来事を起こす

_EVENT_TEXT_INSTRUCTION = (
    "直近のeventのリストから、状況を把握する。年齢、性別、性格、emotion、"
    "textをベースに人物像を推測する。状況と人物像に基づいて、行動を決定"
    "する。キャラクターはそれぞれ、自分や他のキャラクター、場所、オブジェ"
    "クトに影響を与える。" + EVENT_PROGRESSION_INSTRUCTION + EVENT_SCENE_INSTRUCTION
)


_DRIVE_TEXT_INSTRUCTION = (
    "text はその人物の信念・思考の核になる情報として扱う。"
    "出来事なら character_drives 自体を空リストのままにする。"
)

_INVOLVEMENT_INSTRUCTION = (
    "同じ場に複数の人物・個体がいるなら、一人(一個体)だけで完結させず、"
    "その間の対話・衝突・協力などの絡みを積極的に考える。関わった人物・"
    "個体があれば、その id を渡した一覧の中からだけ選んで character_ids /"
    " object_ids に入れる(複数可)。誰も(何も)関わらない出来事ならどちらも"
    "空リストにする。"
)

_CHARACTER_UPDATE_INSTRUCTION = (
    CHARACTER_TEXT_UPDATE_INSTRUCTION + "belong_id はその人物の"
    "所属がこの出来事で変わったときだけ、渡した「居合わせる個体」の id から"
    "選ぶ(変わっていなければキー自体を省く)。"
)

_LOCATION_CHANGE_INSTRUCTION = (
    "この出来事が場所自身や資源の改廃(消滅・新設・枯渇・発見)に及ぶときだけ、"
    "location_abolished / location_founded / resource_depleted / "
    "resource_created を埋める。何も変わっていなければ location_abolished と "
    "resource_depleted は false、location_founded と resource_created は null "
    "のままにする。location_founded の固有名詞は次の基準で名づける。"
    + PLACE_NAMING_INSTRUCTION
)

_PLACE_SYSTEM_PROMPT = (
    "あなたは架空の世界観の中で、ある場所の日々を描写する設定作家です。"
    "その場所自身の情報、そこに居合わせる人物・個体の一覧、その場所の"
    "直近の出来事を渡すので、この時点でこの場所に起きる出来事を1件だけ"
    "考えてください。"
    + _INVOLVEMENT_INSTRUCTION + AVOID_NARO_TEMPLATE_INSTRUCTION +
    "JSON で答えてください。キーは "
    "event_name(出来事の名前), event_kind(出来事の種別。一言。"
    "無ければ空文字), event_text(出来事の内容。" + _EVENT_TEXT_INSTRUCTION + "), "
    "character_ids(関わった人物の id のリスト。渡した「居合わせる人物」の "
    "id からだけ選ぶ), object_ids(関わった個体の id のリスト。渡した"
    "「居合わせる個体」の id からだけ選ぶ), "
    "character_drives(関わった人物のうち、情動・欲求が動いた者だけのリスト。"
    "各要素は character_id(対象の人物 id), text(" + _DRIVE_TEXT_INSTRUCTION +
    "), level(その情動の強さ。1〜10の整数)の三つ), "
    "character_updates(関わった人物のうち、この出来事で人物レコード自体が"
    "変わった者だけのリスト。各要素は character_id(対象の人物 id)と、"
    + _CHARACTER_UPDATE_INSTRUCTION + "), "
    "location_abolished(bool。この出来事でこの場所自体が消滅・放棄されたか), "
    "location_founded(この出来事でこの場所の配下に新しい場所が生まれたなら "
    "{name, kind, text, environment}。無ければ null), "
    + _LOCATION_CHANGE_INSTRUCTION
)


def _should_roll(time: Stamp) -> bool:
    """3日毎にロールする(1日を起点に、その日から3日刻み)。"""
    return (time.day - 1) % EVENT_ROLL_INTERVAL_DAYS == 0


def _end_after_years(start: Stamp, years: int) -> Stamp:
    return Stamp(start.year + max(years, 1), start.month, start.day,
                 start.hour, start.minute, start.second)


def _append_character_note(character: Character, note: str) -> None:
    """人物の `text` に、生成時の基礎説明を残したまま直近の追記だけを積み足す。

    上限が無いと、一度紛れ込んだ比喩・語彙が消えずにこの人物が関わる全ての
    将来の生成へ永久に持ち込まれ続ける(`CHARACTER_NOTE_LIMIT` のコメント
    参照)。先頭の一段(基礎説明)は常に残し、追記は直近
    `CHARACTER_NOTE_LIMIT - 1` 件までに切り詰める。
    """
    if not character.text:
        character.text = note
        return
    base, *notes = character.text.split(CHARACTER_NOTE_SEPARATOR)
    notes.append(note)
    notes = notes[-(CHARACTER_NOTE_LIMIT - 1):] if CHARACTER_NOTE_LIMIT > 1 else []
    character.text = CHARACTER_NOTE_SEPARATOR.join([base, *notes])


def _current_place_id(session: Session, character: Character, time: Stamp) -> int | None:
    place = session.scalars(
        common_query.character_place_select(character.id, time)).first()
    return place.location_id if place else character.born_place_id


def _current_object_place_id(session: Session, obj: Object, time: Stamp) -> int | None:
    place = session.scalars(
        common_query.object_place_select(obj.id, time)).first()
    return place.location_id if place else obj.root_place_name


def _group_by_place(
    session: Session, time: Stamp,
) -> dict[int, tuple[list[Character], list[Object]]]:
    """**その時点で生きている人物・個体を、いま居る場所ごとにまとめる。**

    居場所の記録(`character_place` / `object_place`)が無いものは、
    出自の場所(`born_place_id` / `root_place_name`)に居るとみなす
    (`_current_place_id` `_current_object_place_id` と同じ扱い)。
    """
    grouped: dict[int, tuple[list[Character], list[Object]]] = defaultdict(
        lambda: ([], []))

    characters = session.scalars(
        world_createion_query.alive_characters_select(time)).all()
    for character in characters:
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


def _progress_place(
    session: Session, place_id: int,
    characters: list[Character], objects: list[Object], time: Stamp,
) -> Event | None:
    recent_events = session.scalars(
        common_query.events_of_select(place_id, until=time, limit=RECENT_EVENT_LIMIT)
    ).all()
    place = session.get(Location, place_id)
    plots = story_createion_query.load_location_plot(session, place_id, time)

    prompt = (
        f"場所id: {place_id}\n"
        f"場所の情報: {(place.name, place.kind, place.text) if place else None}\n"
        f"居合わせる人物: {[(c.id, c.name, c.tone, c.text) for c in characters[:20]]}\n"
        f"居合わせる個体: {[(o.id, o.name, o.text) for o in objects[:20]]}\n"
        f"直近の出来事(名前, 種別): {[(e.name, e.kind) for e in recent_events]}\n"
        f"進めたい筋書き: {[p.text for p in plots] or '(指定なし)'}\n"
        f"現在の時刻: {time}\n"
        "この場所に、この時点で起きる出来事を1件、決めてください。"
        + ("進めたい筋書きがあるなら、そこへ向かう一歩になる出来事を優先する。"
           if plots else "")
    )
    decided = ai_client.try_generate_json(prompt, system=_PLACE_SYSTEM_PROMPT)

    if not decided.get("event_name"):
        return None

    character_ids = {c.id: c for c in characters}
    object_ids = {o.id: o for o in objects}

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

    record = Event(
        name=decided["event_name"],
        kind=decided.get("event_kind") or "",
        text=decided.get("event_text") or "",
        time=time,
        location_id=place_id,
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
            _append_character_note(character, update["text"])
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
        random_location_resource_generator.generate_for_new_location(session, new_location, time)
        location_notes.append(f"{new_location.name}(id={new_location.id}): 新設")

    resource_notes = []
    if decided.get("resource_depleted"):
        depleted = session.scalars(
            world_createion_query.active_resources_select(place_id, time)
        ).all()
        for resource in depleted:
            resource.end = time
        if depleted:
            resource_notes.append(f"既存資源{len(depleted)}件が枯渇")

    created_resource = decided.get("resource_created")
    if isinstance(created_resource, dict) and created_resource.get("kind"):
        years = int(created_resource.get("years") or 50)
        draft = build_location_resource(
            location_id=place_id,
            kind=created_resource.get("kind"),
            quantity=int(created_resource.get("quantity") or 1000),
            unit=created_resource.get("unit") or "単位",
            text=created_resource.get("text") or "",
            start=time,
            end=_end_after_years(time, years),
        )
        session.add(LocationResource(**draft))
        resource_notes.append(f"{draft['kind']} {draft['quantity']}{draft['unit']} 発見")

    session.commit()
    when = format_time(time)
    involved_names = [
        name for name in (
            [character_ids[cid].name for cid in involved_character_ids]
            + [object_ids[oid].name for oid in involved_object_ids]
        ) if name
    ]
    print(f"[time_keepr/event] {when} 場所id={place_id}: "
          f"{record.name}({record.kind}) {record.text}"
          + (f" / 関わった: {', '.join(involved_names)}" if involved_names else "")
          + (f" / 情動: {'; '.join(drive_notes)}" if drive_notes else "")
          + (f" / 人物更新: {'; '.join(update_notes)}" if update_notes else "")
          + (f" / 場所: {'; '.join(location_notes)}" if location_notes else "")
          + (f" / 資源: {'; '.join(resource_notes)}" if resource_notes else ""))
    return record


def generate_random(session: Session, time: Stamp) -> list[Event]:
    """3日毎に、人物・個体が居る場所それぞれについて出来事を進行させる。"""
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
            event = _progress_place(session, place_id, characters, objects, time)
            if event is not None:
                created.append(event)

    return created
