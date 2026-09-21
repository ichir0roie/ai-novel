#!/usr/bin/env python3
"""世界の側の人物を、時の流れの中で自動的に増やす。

`generate_random`: 月初に確率 `constants.CHARACTER_PROBABILITY` で場所を一つ選び、人物を一件生む(既定では毎月一人)。
候補地はプロット(`Plot`)が一件も無い場所を外し、生んだ人物にはその人物専用の
筋書き(`CharacterPlot`)を一件添えて db へ確定する。
"""
from __future__ import annotations

import random

from sqlalchemy import and_, func, select

from DEM.ai_instructions.naming import CHARACTER_NAMING_INSTRUCTION
from DEM.data_access_logic.query import common_query, story_createion_query, world_createion_query
from DEM.data_access_logic.query.base import character_time_condition, plot_time_condition
from DEM.db.schema import *
from DEM.local_ai import ai_client
from DEM.local_ai.time_keeper import constants
from DEM.local_ai.time_keeper._format import format_time
from DEM.randomizer.random_character_generator import build_character

_CONTENT_SYSTEM_PROMPT = (
    "あなたは架空の世界観を構築する設定作家です。"
    "新しく生まれる人物1件について、人物説明・年齢・今後の筋書きを、"
    "自然な日本語で JSON で答えてください。"
    f"年齢(age)は{constants.CHARACTER_AGE_RANGE[0]}〜{constants.CHARACTER_AGE_RANGE[1]}歳の範囲で、"
    "text の人物説明と矛盾しないように、あなた自身で決めてください"
    "(例えば老成した説明なら年長めに、幼さの残る説明なら年少めに)。"
    "この人物が目立った能力・特技を持つのが自然なら、その内容を text の"
    "人物説明の中に地の文として書き込んでください(能力を別項目には分けない)。"
    "渡す場所の説明・参考地域・参考文化・参考時代や、所属する地域、"
    "その場所・時刻に関連する筋書きに、この人物の生活・仕事・性格が"
    "自然に馴染むよう考慮してください(参考地域・参考文化・参考時代は、"
    "固有名詞をそのまま持ち込むのではなく、地理・気候・生業・価値観の"
    "手がかりとして使ってください)。"
    "「この人物が体現する要素」が渡されているときは、複数の立場のうち"
    "あなたが選びやすいものへ寄せず、渡された要素をこの人物の生き方の核として"
    "必ず反映してください。"
    "「既にいる人物」「既にある個体」が渡されているときは、その役割・関係・"
    "特徴とは重ならない人物にしてください(同じ立場・同じ能力・同じ関係性の"
    "作り直しをしない)。"
    "plot は、この人物個人について今後たどってほしい筋書き。text の人物説明と"
    "矛盾しない範囲で、起・承・転・結の四つの段階を、この順に、それぞれ"
    "一〜二文ずつ改行で区切って書く。"
    "起は、今の立場と、この人物が抱えている問題・欲求。"
    "承は、その問題・欲求が誰と何を巡ってどう広がるか。"
    "転は、それを決定的に動かす転機(対立・裏切り・喪失・選択など)。"
    "結は、その転機を経てこの人物がどこに行き着くか(成功・失敗・変質、"
    "どれでもよい)。"
    "起だけを書いて終わらせず、四つの段階を必ず全部埋める。各段階は、"
    "誰と・何を巡って、が分かる具体的な内容にする。"
    "出来事生成のたびに読まれ、その人物が関わる出来事の展開の優先材料になる。"
    "キーは text(具体的な生活・仕事・関係が伝わる2〜3文の人物説明。能力・"
    "特技があれば含む。「優しい」「謎めいた」のような、誰にでも当てはまる"
    "抽象的な形容だけで済ませず、この人物固有の具体的な癖・関わり・生い立ちを"
    "最低一つ含める), age(年齢, 整数), plot(今後の筋書き)の三つだけ。"
)

_CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "age": {"type": "integer", "minimum": constants.CHARACTER_AGE_RANGE[0], "maximum": constants.CHARACTER_AGE_RANGE[1]},
        "plot": {"type": "string"},
    },
    "required": ["text", "age", "plot"],
    "additionalProperties": False,
}

_NAME_SYSTEM_PROMPT = (
    "あなたは架空の世界観を構築する設定作家です。"
    "内容が決まっている人物1件に、名前と読みだけを付けます。"
    + CHARACTER_NAMING_INSTRUCTION +
    "渡す人物説明・年齢・筋書き・体格や口調から連想できる、この人物に似合う"
    "名前にしてください。"
    "居場所・場所の特徴・所属する地域が渡されているときは、その参考地域・"
    "参考文化・参考時代を名の響きや漢字・カタカナの選び方の手がかりにして、"
    "同じ場所の人物として馴染む名にしてください(固有名詞をそのまま持ち込まない)。"
    "「既にいる人物の名」が渡されているときは、頭の音や拍数がそれらと"
    "重ならないようにしてください。"
    "キーは name(名前), read(読み)の二つだけ。"
)

_NAME_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "read": {"type": "string"},
    },
    "required": ["name", "read"],
    "additionalProperties": False,
}


def _should_roll(time: Stamp) -> bool:
    """月に一度、月初(1日)にだけロールする。"""
    return time.day == 1


def _region_label(session: Session, born_place: Location | None) -> str:
    """`born_place` が所属する、一つ上の地域の名前(無ければ「不明」)。"""
    if born_place is None or born_place.parent_id is None:
        return "不明"
    parent = session.get(Location, born_place.parent_id)
    if parent is None:
        return "不明"
    return f"{parent.name}({parent.kind})"


def _plot_texts(session: Session, born_place: Location | None, time: Stamp) -> list[str]:
    """`born_place` とその祖先、`time` に関連する筋書きの本文。"""
    if born_place is None:
        return []
    plots = story_createion_query.load_location_plot(session, born_place.id, time)
    return [plot.text for plot in plots if plot.text]


_ELEMENT_SYSTEM_PROMPT = (
    "あなたは筋書きの構成を分析する設定作家です。"
    "渡す筋書きの本文から、その筋書きの中で人物が生きうる、互いに重ならない"
    "具体的な立場・職業・関わり方を箇条書きで抜き出してください。"
    "筋書きが複数の立場を挙げている場合は、それぞれを一つずつの要素にして"
    "漏らさず拾ってください。"
    "キーは elements(文字列の配列)だけです。"
)

_ELEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "elements": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["elements"],
    "additionalProperties": False,
}


def _plot_elements(plot_texts: list[str]) -> list[str]:
    """`plot_texts` それぞれから、体現しうる人物像の要素を抜き出して集める。

    抜き出し(この関数)と選択(呼び出し側の `rng.choice`)を分けることで、
    複数の立場を持つ筋書きでも生成のたびランダムに割り振られるようにし、
    モデルが生成時に自由選択して同じ立場へ偏るのを防ぐ。
    """
    elements: list[str] = []
    for text in plot_texts:
        decided = ai_client.try_generate_json(
            text, _ELEMENT_SCHEMA, system=_ELEMENT_SYSTEM_PROMPT)
        elements.extend(
            e.strip() for e in decided.get("elements", []) if e and e.strip())
    return elements


def _nearby_place_ids(session: Session, born_place: Location | None) -> list[int]:
    """`born_place` 自身と、その祖先の場所 id。無ければ空。"""
    if born_place is None:
        return []
    return [node["id"] for node in common_query.place_path(session, born_place.id)]


def _nearby_characters(session: Session, born_place: Location | None, time: Stamp) -> list[Character]:
    """`born_place` かその祖先に、`time` 時点で居る人物。重複回避の材料にする。"""
    place_ids = _nearby_place_ids(session, born_place)
    if not place_ids:
        return []
    ids = session.scalars(common_query.resident_character_ids_select(place_ids, time)).all()
    if not ids:
        return []
    return session.scalars(select(Character).where(Character.id.in_(ids))).all()


def _nearby_objects(session: Session, born_place: Location | None, time: Stamp) -> list[Object]:
    """`born_place` かその祖先に、`time` 時点で居る個体(群)。重複回避の材料にする。"""
    place_ids = _nearby_place_ids(session, born_place)
    if not place_ids:
        return []
    ids = session.scalars(common_query.resident_object_ids_select(place_ids, time)).all()
    if not ids:
        return []
    return session.scalars(select(Object).where(Object.id.in_(ids))).all()


def _record_context(records: list) -> str:
    """人物・個体のリストを、名前と説明の箇条書きにする。"""
    if not records:
        return "(無し)"
    return "\n".join(f"- {r.name}: {r.text or '(説明なし)'}" for r in records)


def _character_names(characters: list[Character]) -> str:
    """人物のリストを、名前(読み)の一覧にする。命名時の重複回避に使う。"""
    if not characters:
        return "(無し)"
    return "、".join(f"{c.name}({c.read})" if c.read else c.name for c in characters)


def _location_context(place: Location | None) -> str:
    """**人物の特徴を考える材料になる、場所の `text` と参考カラム。**

    `text`(場所の説明)に加え、`sample_region` `sample_culture` `sample_era`
    (参考にした実在の地域・文化・時代)があれば並べる。人物の性格・生業を
    決めるとき、この場所固有の手がかりとして使う。
    """
    if place is None:
        return "(不明)"
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


def _generate_one(
    session: Session, born_place: Location | None, time: Stamp, rng: random.Random,
) -> Character:
    """**人物を一件、db へ確定して返す。** ロール判定(当たり外れ)は呼び出し側の責任。"""
    draft = build_character()

    region_label = _region_label(session, born_place)
    plot_texts = _plot_texts(session, born_place, time)
    plot_label = "\n".join(f"- {text}" for text in plot_texts) or "(無し)"

    elements = _plot_elements(plot_texts)
    chosen_element = rng.choice(elements) if elements else None
    element_line = (
        f"この人物が体現する要素(必ずこれに基づいて生活・仕事を決める): {chosen_element}\n"
        if chosen_element else ""
    )

    nearby_characters = _nearby_characters(session, born_place, time)
    nearby_objects = _nearby_objects(session, born_place, time)

    content_prompt = (
        f"出身: {born_place.name if born_place else '不明'}\n"
        f"出身地の特徴:\n{_location_context(born_place)}\n"
        f"地域: {region_label}\n"
        f"性別: {draft['sex']} / 体格: {draft['build']} / 口調: {draft['tone']}\n"
        f"現在の時刻: {time}\n"
        f"年齢は{constants.CHARACTER_AGE_RANGE[0]}〜{constants.CHARACTER_AGE_RANGE[1]}歳の範囲で、text の人物説明に"
        "似合う歳を選んでください。\n"
        f"この場所・時刻に関連する筋書き:\n{plot_label}\n"
        f"{element_line}"
        f"既にいる人物:\n{_record_context(nearby_characters)}\n"
        f"既にある個体:\n{_record_context(nearby_objects)}\n"
        "この場所に自然な人物を1件、決めてください。"
    )
    decided = ai_client.try_generate_json(content_prompt, _CONTENT_SCHEMA, system=_CONTENT_SYSTEM_PROMPT)

    draft["text"] = decided.get("text") or draft["text"]
    try:
        age = int(decided.get("age", 0))
    except (TypeError, ValueError):
        age = rng.randint(*constants.CHARACTER_AGE_RANGE)
    age = min(max(age, constants.CHARACTER_AGE_RANGE[0]), constants.CHARACTER_AGE_RANGE[1])

    dead_age = age + rng.randint(10, 100)

    draft["start"] = Stamp(time.year - age)
    draft["end"] = Stamp(time.year - age + dead_age)
    plot_text = (decided.get("plot") or "").strip() or draft["text"]

    # 名前は、人物説明・年齢・筋書きなど中身が決まったあとに、その内容から連想して決める。
    name_prompt = (
        f"人物説明: {draft['text']}\n"
        f"年齢: {age}\n"
        f"筋書き: {plot_text}\n"
        f"性別: {draft['sex']} / 体格: {draft['build']} / 口調: {draft['tone']}\n"
        f"居場所: {born_place.name if born_place else '不明'}\n"
        f"場所の特徴:\n{_location_context(born_place)}\n"
        f"所属する地域: {region_label}\n"
        f"既にいる人物の名: {_character_names(nearby_characters)}\n"
        "この人物に似合う名前と読みを決めてください。"
    )
    named = ai_client.try_generate_json(name_prompt, _NAME_SCHEMA, system=_NAME_SYSTEM_PROMPT)
    draft["name"] = named.get("name") or draft["name"]
    draft["read"] = named.get("read") or draft["read"]

    record = Character(**draft)
    session.add(record)
    session.flush()  # plot/place から character_id で参照するため、先に id を確定する

    if born_place is not None:
        session.add(CharacterPlace(
            character_id=record.id, location_id=born_place.id,
            start=record.start, end=record.end))

    # 生んだ人物には必ず一件、専用の筋書き(CharacterPlot)を添える。
    session.add(CharacterPlot(character_id=record.id, text=plot_text, start=time))

    session.commit()
    when = format_time(time)
    place_label = f"{born_place.name}(id={born_place.id})" if born_place else "不明"
    print(f"[time_keepr/character] {when} 生成: {record.name}({record.read})"
          f" id={record.id} 出自={place_label} 年齢={age}\n"
          f"    性別: {record.sex} / 体格: {record.build} / 口調: {record.tone}\n"
          f"    筋書きの要素: {chosen_element or '(無し)'}\n"
          f"    筋書き: {plot_text}\n"
          f"    説明: {record.text or '(説明なし)'}")
    return record


def get_usable_location_q(time: Stamp):
    """`time` の時点で有効なプロットを持ち、居る人物数がまだ許容範囲未満の場所の id。"""
    return (
        select(Location.id)
        .join(Plot, Plot.location_id == Location.id)
        .outerjoin(
            CharacterPlace,
            and_(CharacterPlace.location_id == Location.id, character_time_condition(time)),
        )
        .outerjoin(
            Character, Character.id == CharacterPlace.character_id
        )
        .outerjoin(
            CharacterPlot, Character.id == CharacterPlot.character_id
        )
        .where(
            or_(Location.start.is_(None), Location.start <= time),
            or_(Location.end.is_(None), Location.end > time),
            plot_time_condition(time),
            character_time_condition(time),
        )
        .group_by(Location.id)
        .having(
            func.count(CharacterPlot.character_id.distinct()) < constants.MAX_CHARACTER_PLOT_PER_LOCATION
        )
    )


def generate_random(session: Session, time: Stamp) -> Character | None:
    """ロールに当たったら、人物を一件 db へ確定して返す。当たらなければ None。"""
    if not _should_roll(time):
        return None

    seed = random.randrange(10 ** 9)
    rng = random.Random(seed)
    roll = rng.random()
    when = format_time(time)
    if roll >= constants.CHARACTER_PROBABILITY:
        print(f"[time_keepr/character] {when} 月初判定: "
              f"seed={seed} roll={roll:.4f} >= {constants.CHARACTER_PROBABILITY} → 見送り")
        return None
    print(f"[time_keepr/character] {when} 月初判定: "
          f"seed={seed} roll={roll:.4f} < {constants.CHARACTER_PROBABILITY} → 生成")

    # born_place も、この時刻にまだ存在している場所だけを候補にする。
    # プロットが無い場所・人物数が既に上限に達している場所は選ばない。
    usable_location_q = get_usable_location_q(time)
    eligible_places = session.scalars(select(Location).where(Location.id.in_(usable_location_q))).all()
    if not eligible_places:
        print(f"[time_keepr/character] {when} 空きのある場所が無いため見送り")
        return None
    born_place = rng.choice(eligible_places)

    return _generate_one(session, born_place, time, rng)
