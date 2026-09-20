#!/usr/bin/env python3
"""**場所・時刻ごとに、その場に居合わせる人物・個体を巻き込んだ出来事を起こす。**

`DEM.local_ai.time_keeper.main` の常駐ループから毎日呼ばれる。
`random_character_generator` `random_location_generator` と同じ理由で、
claude を介さず db への確定まで一度に行う(内容の判断だけをローカル
AI(`ai_client`)に委ねる)。

**人物・個体を一件ずつ順に回すのではなく、場所を軸に回す。** 「1月に一度、
月初に、その時点で人物・個体が居る場所それぞれについて一定の確率で」
出来事を一件起こす。その場所に居合わせる人物・個体の一覧と、その場所の
直近の出来事をまとめて渡し、その中の誰が(何が)関わったかをまとめて
1回の呼び出しで決めさせる。**一人(一個体)だけで完結する出来事に閉じず、
同じ場に複数の人物・個体がいれば、その間の絡み(対話・衝突・協力)を
積極的に拾わせる**のが、人物ごとに独立して回していた前の実装との違い
(絡みが起きにくかった問題への対応)。

出来事に関わった人物ぶんだけ、`DEM/claude_interface/randomizer/commit_event.py`
の `character_drives` `character_skills` と同じ形で、情動
(`CharacterEmotion`。テーブル名は `character_drive`)の変化と技
(`CharacterSkill`)の熟練度もその場でまとめて記録できる(個体には情動・技の
欄が無いので、個体側はそこまでで止める)。中間レコード
(`EventCharacter` `EventObject`)は、AI が渡した一覧の中から選べた id の
ぶんだけ作る(一覧に無い id は無視する)。

**情動(`character_drives`)は、その人物の信念・思考の核になる情報として
扱う(`IHG/chronicle.md`「人物感情は…」)。** 毎月ロールする日常の出来事の
たびに積み増すものではなく、その人物にとって信念を揺らすほど大きな出来事の
ときだけ動かす。それ以外はローカル AI に空リストのまま返させる
(`_DRIVE_TEXT_INSTRUCTION`)。**同じ人物に既に動いている情動(`end` が
まだ無いもの)があれば、新しい行を積み増さずにその一件の `text` `level`
を更新する。**

技は**新しく作らない**。名づけ(`IHG/naming.md`)が要る判断なので、
既にある技(`Skill`)の中から AI に選ばせるだけにとどめる。当てはまる
ものが無ければ、その出来事の技の伸びは見送る。**同じ人物が同じ技を
既に持っていれば(`CharacterSkill` が既にあれば)、行を増やさずに
`level`(熟練度)だけを更新する。**

場所自身の情報(名前・種別・text)も人物・個体の一覧と一緒に渡す。
出来事の内容によって人物レコード自体(`Character.text` 一言の現状、
`Character.belong_id` 所属)が変わったときは、`character_updates`
(`[{character_id, text?, belong_id?}]`)としてまとめて返させ、
その場で db に反映する(変わっていない人物は含めない。技名の新規作成と
同様、ここも既にある `Object` の id から選ぶだけで新規は作らない)。

`event_text` は `commit_event`(`DEM/claude_interface/randomizer/commit_event.py`)
と同じ基準に揃える。要約で済ませず、**軽い小説として1000文字程度**で
思考・行動・影響を場面として書かせる(`IHG/chronicle.md`「出来事の text は
場面で書く」)。プロンプト側の指示は `_EVENT_TEXT_INSTRUCTION` に持つ。
"""
from __future__ import annotations

import random
from collections import defaultdict

from sqlalchemy import select

from DEM.data_access_logic.query import (
    common_query, world_createion_query,
)
from DEM.db.schema import (
    Character, CharacterEmotion, CharacterSkill, Event, EventCharacter,
    EventObject, Location, Object, Session, Skill, Stamp,
)
from DEM.local_ai import ai_client
from DEM.local_ai.time_keeper._format import format_time

PLACE_PROBABILITY = 0.15  # 月に一度、人物・個体が居る場所1件につき15%の確率で

_EVENT_TEXT_INSTRUCTION = (
    "event_text は要約(「〜という出来事があった」)で済ませない。"
    "軽い小説として1000文字程度で、その時その場の思考・行動・"
    "(この出来事が及ぼす)影響を、場面として書く。"
)

_DRIVE_TEXT_INSTRUCTION = (
    "text はその人物の信念・思考の核になる情報として扱う。この出来事が"
    "信念を揺らすほど大きいときだけ、動いた情動・欲求を書く。日常の細かな"
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
    "text はその人物の現状を一言で言い直したもの(直近の様子・立場が"
    "この出来事で変わったときだけ書く。変わっていなければこの人物自体を"
    "character_updates に含めない)。belong_id はその人物の所属が"
    "この出来事で変わったときだけ、渡した「居合わせる個体」の id から選ぶ"
    "(変わっていなければキー自体を省く)。"
)

_PLACE_SYSTEM_PROMPT = (
    "あなたは架空の世界観の中で、ある場所の日々を描写する設定作家です。"
    "その場所自身の情報、そこに居合わせる人物・個体の一覧、その場所の"
    "直近の出来事を渡すので、この時点でこの場所に起きる出来事を1件だけ"
    "考えてください。"
    + _INVOLVEMENT_INSTRUCTION +
    "JSON で答えてください。キーは "
    "event_name(出来事の名前), event_kind(出来事の種別。一言。"
    "無ければ空文字), event_text(出来事の内容。" + _EVENT_TEXT_INSTRUCTION + "), "
    "character_ids(関わった人物の id のリスト。渡した「居合わせる人物」の "
    "id からだけ選ぶ), object_ids(関わった個体の id のリスト。渡した"
    "「居合わせる個体」の id からだけ選ぶ), "
    "character_drives(関わった人物のうち、情動・欲求が動いた者だけのリスト。"
    "各要素は character_id(対象の人物 id), text(" + _DRIVE_TEXT_INSTRUCTION +
    "), level(その情動の強さ。1〜10の整数)の三つ), "
    "character_skills(関わった人物のうち、技が伸びた者だけのリスト。各要素は"
    "character_id(対象の人物 id), skill_name(伸びた技の名前。渡した技の"
    "候補の中からだけ選ぶ), level(その技の熟練度。1〜10の整数)の三つ), "
    "character_updates(関わった人物のうち、この出来事で人物レコード自体が"
    "変わった者だけのリスト。各要素は character_id(対象の人物 id)と、"
    + _CHARACTER_UPDATE_INSTRUCTION + ")"
    "の七つだけ。"
)


def _should_roll(time: Stamp) -> bool:
    """月に一度、月初(1日)にだけロールする。"""
    return time.day == 1


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
        common_query.events_of_select(place_id, until=time, limit=10)
    ).all()
    catalog = session.scalars(select(Skill)).all()
    place = session.get(Location, place_id)

    prompt = (
        f"場所id: {place_id}\n"
        f"場所の情報: {(place.name, place.kind, place.text) if place else None}\n"
        f"居合わせる人物: {[(c.id, c.name, c.tone, c.text) for c in characters[:20]]}\n"
        f"居合わせる個体: {[(o.id, o.name, o.text) for o in objects[:20]]}\n"
        f"直近の出来事: {[e.name for e in recent_events]}\n"
        f"選べる技の候補: {sorted(s.name for s in catalog)}\n"
        f"現在の時刻: {time}\n"
        "この場所に、この時点で起きる出来事を1件、決めてください。"
    )
    decided = ai_client.try_generate_json(prompt, system=_PLACE_SYSTEM_PROMPT)

    if not decided.get("event_name"):
        return None

    character_ids = {c.id: c for c in characters}
    object_ids = {o.id: o for o in objects}

    def _valid_ids(raw, pool: dict[int, object]) -> list[int]:
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
        place_id=place_id,
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
            character_id = int(drive.get("character_id"))
        except (TypeError, ValueError):
            continue
        text = drive.get("text")
        if character_id not in character_ids or not text:
            continue
        level = int(drive.get("level") or 1)
        # 同じ人物に既に動いている情動(end が無いもの)があれば、
        # 積み増さずにその一件を更新する。
        existing_drive = session.scalar(
            select(CharacterEmotion).where(
                CharacterEmotion.character_id == character_id,
                CharacterEmotion.end.is_(None),
            )
        )
        if existing_drive is not None:
            existing_drive.text = text
            existing_drive.level = level
        else:
            session.add(CharacterEmotion(
                character_id=character_id, text=text,
                level=level, start=time, end=None,
            ))
        drive_notes.append(f"{character_ids[character_id].name}: {text}")

    skill_notes = []
    for growth in decided.get("character_skills") or []:
        if not isinstance(growth, dict):
            continue
        try:
            character_id = int(growth.get("character_id"))
        except (TypeError, ValueError):
            continue
        skill_name = growth.get("skill_name")
        if character_id not in character_ids or not skill_name:
            continue
        skill = session.scalar(select(Skill).where(Skill.name == skill_name))
        if skill is None:
            print(f"[time_keepr/event] 既存に無い技名 {skill_name!r} は見送り")
            continue
        level = int(growth.get("level") or 1)
        # 同じ人物が同じ技を既に持っていれば、行を増やさずに熟練度だけ更新する。
        existing_skill = session.scalar(
            select(CharacterSkill).where(
                CharacterSkill.character_id == character_id,
                CharacterSkill.skill_id == skill.id,
            )
        )
        if existing_skill is not None:
            existing_skill.level = level
        else:
            session.add(CharacterSkill(
                character_id=character_id, skill_id=skill.id, level=level,
            ))
        skill_notes.append(f"{character_ids[character_id].name}: {skill_name}(lv{level})")

    update_notes = []
    for update in decided.get("character_updates") or []:
        if not isinstance(update, dict):
            continue
        try:
            character_id = int(update.get("character_id"))
        except (TypeError, ValueError):
            continue
        character = character_ids.get(character_id)
        if character is None:
            continue
        applied = []
        if update.get("text"):
            character.text = update["text"]
            applied.append(f"text={update['text']}")
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

    session.commit()
    when = format_time(time)
    involved_names = (
        [character_ids[cid].name for cid in involved_character_ids]
        + [object_ids[oid].name for oid in involved_object_ids]
    )
    print(f"[time_keepr/event] {when} 場所id={place_id}: "
          f"{record.name}({record.kind}) {record.text}"
          + (f" / 関わった: {', '.join(involved_names)}" if involved_names else "")
          + (f" / 情動: {'; '.join(drive_notes)}" if drive_notes else "")
          + (f" / 技: {'; '.join(skill_notes)}" if skill_notes else "")
          + (f" / 人物更新: {'; '.join(update_notes)}" if update_notes else ""))
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
            event = _progress_place(session, place_id, characters, objects, time)
            if event is not None:
                created.append(event)

    return created
