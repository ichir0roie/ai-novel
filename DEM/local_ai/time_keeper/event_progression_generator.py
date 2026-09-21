#!/usr/bin/env python3
"""**場所・時刻ごとに、その場に居合わせる人物・個体を巻き込んだ出来事を起こす。**

出来事には `start`〜`end`(進行中と見なす幅)を持たせる。`end` はローカル
AI が決める `event_duration_days`(`EVENT_DURATION_INSTRUCTION`)を `start`
に足して組む。**進行中の出来事がある人物は、`end` を過ぎるまで次の出来事の
対象にしない**(`_group_by_place` が `world_createion_query.busy_character_ids_select`
で除く)。これが無いと、同じ人物が3日おきのロールのたび毎回新しい出来事に
巻き込まれ、前の出来事がまだ続いているはずの間にも次々と話が進んでしまう。

**人物だけでなく、国・組織のような個体(`Object`)も行為の主体として扱う。**
出来事は、その時その場に居合わせるもの(人物・個体・場所・資源)同士の
相互関係から立てる(`EVENT_RELATION_INSTRUCTION` `OBJECT_ACTION_INSTRUCTION`)。
個体の `text` も、人物と同じように `object_updates` で積み足す
(`OBJECT_TEXT_UPDATE_INSTRUCTION`)。

**その場に今いる顔ぶれだけでは、内輪の合意・対立で閉じ続けて動かなく
なることがある。** そこで候補を二段構えにする。(1) `_reach_objects` が、
「一つ上の圏内」(`read_cast` と同じ考え方。`common_query.place_up` /
`descendant_place_ids`)に拠点を持つ個体を、今は居合わせなくても遠隔で
働きかけてくる候補として渡す。(2) それでも噛み合う主体が無いときは、
`object_founded` でローカル AI 自身に新しい個体を出来事の中で誕生させて
よい(`_OBJECT_FOUND_INSTRUCTION`)。どちらも
`EVENT_PROGRESSION_INSTRUCTION` が「同じ内輪の顔ぶれだけで何度も閉じない」
の受け皿として使う。

`text` は小説ではなく**情報整理のための記録**として書かせる
(`EVENT_RECORD_INSTRUCTION`)。文体・セリフは本文(話)の側で決める。
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
    EVENT_RELATION_INSTRUCTION, OBJECT_ACTION_INSTRUCTION,
    OBJECT_TEXT_UPDATE_INSTRUCTION, RECENT_EVENT_LIMIT,
)
from DEM.ai_instructions.naming import PLACE_NAMING_INSTRUCTION, TERM_NAMING_INSTRUCTION
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
from DEM.local_ai.time_keeper._format import add_days, format_time
from DEM.local_ai.time_keeper.random_object_generator import (
    _DEFAULT_SCALE, _SCALE_INFLUENCE,
)
from DEM.randomizer.random_location_generator import build_location
from DEM.randomizer.random_location_resource_generator import (
    build_location_resource,
)
from DEM.randomizer.random_object_generator import build_object

EVENT_ROLL_INTERVAL_DAYS = 3  # 3日毎に、人物・個体が居る場所それぞれでロールする
PLACE_PROBABILITY = 0.10  # ロールのたび、場所1件につき10%の確率で出来事を起こす

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
    "個体も、自分や他の人物・個体・場所・資源に影響を与える。"
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
    "この出来事が場所自身や資源の改廃(消滅・新設・枯渇・発見)に及ぶときだけ、"
    "location_abolished / location_founded / resource_depleted / "
    "resource_created を埋める。何も変わっていなければ location_abolished と "
    "resource_depleted は false、location_founded と resource_created は null "
    "のままにする。location_founded の固有名詞は次の基準で名づける。"
    + PLACE_NAMING_INSTRUCTION
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
    "id からだけ選ぶ), object_ids(関わった個体の id のリスト。渡した"
    "「居合わせる個体」と「一つ上の圏内の個体」の id からだけ選ぶ), "
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
    """3日毎にロールする(1日を起点に、その日から3日刻み)。"""
    return (time.day - 1) % EVENT_ROLL_INTERVAL_DAYS == 0


def _end_after_years(start: Stamp, years: int) -> Stamp:
    return Stamp(start.year + max(years, 1), start.month, start.day,
                 start.hour, start.minute, start.second)


def _append_note(record: Character | Object, note: str) -> None:
    """人物・個体の `text` に、生成時の基礎説明を残したまま直近の追記だけを積み足す。

    上限が無いと、一度紛れ込んだ比喩・語彙が消えずにその人物・個体が関わる
    全ての将来の生成へ永久に持ち込まれ続ける(`CHARACTER_NOTE_LIMIT` の
    コメント参照)。先頭の一段(基礎説明)は常に残し、追記は直近
    `CHARACTER_NOTE_LIMIT - 1` 件までに切り詰める。人物と個体で同じ上限・
    同じ区切りを使う。
    """
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

    **進行中の出来事(`start`〜`end` がこの時点を含む)に関わっている人物は
    外す。** その人物が次の出来事に移るのは、今の出来事の `end` を過ぎてから。
    """
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
    """**その場に今いなくても、遠隔から出来事に関与できる個体の候補。**

    `read_cast`(`DEM/claude_interface/story/_rows.py` の `cast`)と同じ
    「一つ上の圏内」(`common_query.place_up` で一段のぼり、
    `descendant_place_ids` でその配下をまるごと拾う)を、`_group_by_place`
    が既に組んだ `grouped` から引く。追加の select は要らない。

    これが無いと、`event_progression_generator` はその場所に**今いる**
    人物・個体からしか出来事を組み立てられず、IP管理団体・規制当局・
    競合のような「今はまだこの場に居ない外部の利害関係者」を出来事に
    巻き込む手段が無い。結果、同じ内輪の顔ぶれだけで「議論して合意する/
    対立する」を繰り返す一因になる(`EVENT_PROGRESSION_INSTRUCTION`)。
    """
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

    prompt = (
        f"場所id: {place_id}\n"
        f"場所の情報: {(place.name, place.kind, place.text) if place else None}\n"
        f"居合わせる人物: {[(c.id, c.name, c.tone, c.text) for c in characters[:20]]}\n"
        f"居合わせる個体(国・組織・集団・物): "
        f"{[(o.id, o.name, o.text, o.world_influence) for o in objects[:20]]}\n"
        f"一つ上の圏内で拠点を持つ個体(今はここに居ないが、遠隔で"
        f"働きかけてくる余地がある候補): "
        f"{[(o.id, o.name, o.text, o.world_influence) for o in reach_objects] or '(無し)'}\n"
        f"直近の出来事(名前): {[e.name for e in recent_events]}\n"
        f"進めたい筋書き: {[p.text for p in plots] or '(指定なし)'}\n"
        f"現在の時刻: {time}\n"
        "この場所に、この時点で起きる出来事を1件、決めてください。"
        "居合わせる人物・個体・場所・資源のうち、どれとどれが噛み合って"
        "この出来事になったのかを踏まえる。"
        + ("進めたい筋書きがあるなら、そこへ向かう一歩になる出来事を優先する。"
           if plots else "")
    )
    decided = ai_client.try_generate_json(prompt, system=_PLACE_SYSTEM_PROMPT)

    if not decided.get("event_name"):
        return None

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
    # 居合わせる個体にも一つ上の圏内の候補にも噛み合う主体が無いとき、
    # ローカル AI がこの出来事の中で新しい個体を誕生させてよい
    # (`_OBJECT_FOUND_INSTRUCTION`)。`random_object_generator.py` と同じ
    # `_SCALE_INFLUENCE` を使い、プロットの無い場所には生まない
    # (`IHG/workflow.md`「プロットの無いエリアに個体を増やさない」)。
    founded_object = decided.get("object_founded")
    if isinstance(founded_object, dict) and founded_object.get("name") and plots:
        scale = founded_object.get("scale")
        if scale not in _SCALE_INFLUENCE:
            scale = _DEFAULT_SCALE
        draft = build_object(root_place_name=place_id)
        draft["name"] = founded_object.get("name") or draft["name"]
        draft["read"] = founded_object.get("read") or draft["read"]
        draft["text"] = founded_object.get("text") or draft["text"]
        draft["world_influence"] = _SCALE_INFLUENCE[scale]
        draft["start"] = time
        new_object = Object(**draft)
        session.add(new_object)
        session.flush()
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
        name=decided["event_name"],
        text=decided.get("event_text") or "",
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
          f"{record.name} {record.text}"
          f" / 継続: {duration_days}日({when}〜{format_time(end)})"
          + (f" / 関わった: {', '.join(involved_names)}" if involved_names else "")
          + (f" / 情動: {'; '.join(drive_notes)}" if drive_notes else "")
          + (f" / 人物・個体更新: {'; '.join(update_notes)}" if update_notes else "")
          + (f" / 新規個体: {'; '.join(object_found_notes)}" if object_found_notes else "")
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
            reach_objects = _reach_objects(
                session, grouped, place_id, {o.id for o in objects})
            event = _progress_place(
                session, place_id, characters, objects, reach_objects, time)
            if event is not None:
                created.append(event)

    return created
