#!/usr/bin/env python3
"""世界の側の人物(と、人物以外の対象)を、時の流れの中で自動的に増やす。

`generate_random`: 月初に確率 `constants.CHARACTER_PROBABILITY` で場所を一つ選び、一件生む。
生む一件は確率 `constants.NON_PERSON_PROBABILITY` で人物以外の対象(国・組織・集団・物など)になり、
どの種別かは AI に選ばせる。候補地はプロット(`Plot`)が一件も無い場所を外し、生んだ一件には
その者専用の筋書き(`CharacterPlot`)を一件添えて db へ確定する。
"""
from __future__ import annotations

import random

from sqlalchemy import and_, func, select, union, union_all
from sqlalchemy.orm import aliased

from DEM.ai.instructions.naming import (
    CHARACTER_NAMING_INSTRUCTION, NAME_PLACEHOLDER, TERM_NAMING_INSTRUCTION,
    fill_name_placeholder,
)
from DEM.ai.instructions.plot_writing import CHARACTER_PLOT_INSTRUCTION, plot_span_instruction
from DEM.ai.instructions.principles import AVOID_NARO_TEMPLATE_INSTRUCTION
from DEM.data_access_logic.query import common_query, story_createion_query, world_createion_query
from DEM.data_access_logic.query.base import *
from DEM.db.schema import *
from DEM.db.schema import PERSONALITY_COLUMNS, PERSONALITY_LEVELS
from DEM.ai.time_keeper._ai import AIClient
from DEM.ai.time_keeper import constants
from DEM.ai.time_keeper._format import format_time
from DEM.randomizer.random_character_generator import build_character

_PLACEHOLDER_INSTRUCTION = (
    f"この一件の名前はまだ決まっていない。text と plot の中でこの一件を指すときは必ず「{NAME_PLACEHOLDER}」と書き、名前を考案して書き込まない。"
)

_AGE_RANGE = f"{constants.GENERATION_CHARACTER_AGE_RANGE[0]}〜{constants.GENERATION_CHARACTER_AGE_RANGE[1]}"

_CONTENT_SYSTEM_PROMPT = f"""\
あなたは架空の世界観を構築する設定作家です。
新しく生まれる人物1件について、人物説明・年齢・今後の筋書きを、自然な日本語で JSON で答えてください。
渡す場所の説明・参考地域・参考文化・参考時代や、所属する地域、その場所・時刻に関連する筋書きに、この人物の生活・仕事・性格が自然に馴染むよう考慮してください(参考地域・参考文化・参考時代は、固有名詞をそのまま持ち込むのではなく、地理・気候・生業・価値観の手がかりとして使ってください)。
「この人物が体現する要素」が渡されているときは、複数の立場のうちあなたが選びやすいものへ寄せず、渡された要素をこの人物の生き方の核として必ず反映してください。
「既にいる人物・対象」が渡されているときは、その役割・関係・特徴とは重ならない人物にしてください(同じ立場・同じ能力・同じ関係性の作り直しをしない)。
「性格」は各軸を {'/'.join(PERSONALITY_LEVELS)} の五段階で渡す(サイコロで決まっていて変えられない)。人物説明と筋書きはこの段階と矛盾しないようにし、「無」「必」の軸はその極端さが生活・仕事・人との関わり方に具体的な癖として表れるように書く。段階の語をそのまま書き写さない。
{CHARACTER_PLOT_INSTRUCTION}
{_PLACEHOLDER_INSTRUCTION}
キーは次の三つだけ。
- text: 具体的な生活・仕事・関係が伝わる2〜3文の人物説明。目立った能力・特技があれば地の文として含め、別項目には分けない。「優しい」「謎めいた」のような、誰にでも当てはまる抽象的な形容だけで済ませず、この人物固有の具体的な癖・関わり・生い立ちを最低一つ含める。
- age: 年齢(整数)。{_AGE_RANGE}の範囲で、text の人物説明と矛盾しない値をあなた自身で決める。例えば老成した説明なら年長めに、幼さの残る説明なら年少めに。
- plot: 今後の筋書き。"""

_CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "age": {"type": "integer", "minimum": constants.GENERATION_CHARACTER_AGE_RANGE[0], "maximum": constants.GENERATION_CHARACTER_AGE_RANGE[1]},
        "plot": {"type": "string"},
    },
    "required": ["text", "age", "plot"],
    "additionalProperties": False,
}

_NON_PERSON_CONTENT_SYSTEM_PROMPT = f"""\
あなたは架空の世界観を構築する設定作家です。
ある場所と、そこに居る人物・既にある対象を渡すので、この場所を拠り所に生まれる人物以外の対象(国・組織・商会・氏族・集団など、まとまりとして動くもの。あるいは物)を1件だけ考え、JSON で答えてください。
渡す場所の産業・地形・人間関係のうち少なくとも一つを具体的に使う。
「この対象が体現する要素」が渡されているときは、渡された要素をこの対象の成り立ちの核として必ず反映してください。
既にある対象と役割が重なるものは作らない。
{CHARACTER_PLOT_INSTRUCTION}
{_PLACEHOLDER_INSTRUCTION}
{AVOID_NARO_TEMPLATE_INSTRUCTION}
キーは次の四つだけ。
- kind: 種別。{' / '.join(constants.NON_PERSON_KINDS)} のいずれか一つ。
- text: この対象が何であって、何を決められて、誰に対して力を持つのかが伝わる2〜3文の説明。「由緒ある」「謎めいた」のような、どの対象にも当てはまる形容だけで済ませない。
- age: 成り立ってからの年数(整数)。{_AGE_RANGE}の範囲。
- plot: 今後の筋書き。"""

_NON_PERSON_CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": list(constants.NON_PERSON_KINDS)},
        "text": {"type": "string"},
        "age": {"type": "integer", "minimum": constants.GENERATION_CHARACTER_AGE_RANGE[0], "maximum": constants.GENERATION_CHARACTER_AGE_RANGE[1]},
        "plot": {"type": "string"},
    },
    "required": ["kind", "text", "age", "plot"],
    "additionalProperties": False,
}

_NAME_SYSTEM_PROMPT = f"""\
あなたは架空の世界観を構築する設定作家です。
内容が決まっている人物1件に、名前だけを付けます。
{CHARACTER_NAMING_INSTRUCTION}
渡す人物説明・年齢・筋書き・体格や口調から連想できる、この人物に似合う名前にしてください。
居場所・場所の特徴・所属する地域が渡されているときは、その参考地域・参考文化・参考時代を名の響きや漢字・カタカナの選び方の手がかりにして、同じ場所の人物として馴染む名にしてください(固有名詞をそのまま持ち込まない)。
キーは name(名前)だけ。"""

_NON_PERSON_NAME_SYSTEM_PROMPT = f"""\
あなたは架空の世界観を構築する設定作家です。
内容が決まっている人物以外の対象(国・組織・集団・物など)1件に、名前だけを付けます。
{TERM_NAMING_INSTRUCTION}
組織の名は場所名か役割名で呼べる形にする。
居場所・場所の特徴・所属する地域が渡されているときは、その参考地域・参考文化・参考時代を名の響きや漢字・カタカナの選び方の手がかりにして、同じ場所のものとして馴染む名にしてください(固有名詞をそのまま持ち込まない)。
「既にいる人物・対象の名」が渡されているときは、それらと紛らわしい名にしない。
キーは name(名前)だけ。"""

_NAME_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
    },
    "required": ["name"],
    "additionalProperties": False,
}

# 人物だけが持つ列。人物以外の対象では空にする。
_PERSON_ONLY_COLUMNS = (
    "sex", "height", "build", "first_person", "second_person", "third_person", "tone",
)


def _should_roll(time: Stamp) -> bool:
    """月に一度、月初(1日)にだけロールする。"""
    return time.day == 1


def _personality_label(values) -> str:
    """性格の 12 軸を「誠実性=高 / 好奇心=並 / …」の一行にする。`values` は辞書でもレコードでもよい。"""
    get = values.get if hasattr(values, "get") else (lambda column: getattr(values, column))
    columns = Character.__table__.columns
    return " / ".join(f"{columns[column].comment}={get(column)}" for column in PERSONALITY_COLUMNS)


def _region_label(session: Session, born_place: Location | None) -> str:
    """`born_place` が所属する、一つ上の地域の名前(無ければ「不明」)。"""
    if born_place is None or born_place.parent_id is None:
        return "不明"
    parent = session.get(Location, born_place.parent_id)
    if parent is None:
        return "不明"
    return f"{parent.name}({parent.kind})"


def _plot_text(session: Session, born_place: Location | None, time: Stamp) -> str:
    """`born_place` とその祖先、`time` に関連する筋書きの本文を、上位の場所から順につなげたもの。"""
    if born_place is None:
        return ""
    return story_createion_query.load_location_plot_text(session, born_place.id, time)


_ELEMENT_SYSTEM_PROMPT = """\
あなたは筋書きの構成を分析する設定作家です。
渡す筋書きの本文から、その筋書きの中で人物が生きうる、互いに重ならない具体的な立場・職業・関わり方を箇条書きで抜き出してください。
筋書きが複数の立場を挙げている場合は、それぞれを一つずつの要素にして漏らさず拾ってください。
キーは elements(文字列の配列)だけです。"""

_ELEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "elements": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["elements"],
    "additionalProperties": False,
}


def _plot_elements(plot_text: str, ai: AIClient) -> list[str]:
    """`plot_text` から、体現しうる人物像の要素を抜き出して集める。

    抜き出し(この関数)と選択(呼び出し側の `rng.choice`)を分けることで、
    複数の立場を持つ筋書きでも生成のたびランダムに割り振られるようにし、
    モデルが生成時に自由選択して同じ立場へ偏るのを防ぐ。
    """
    if not plot_text:
        return []
    decided = ai.try_generate_json(
        plot_text, _ELEMENT_SCHEMA, system=_ELEMENT_SYSTEM_PROMPT)
    return [e.strip() for e in decided.get("elements", []) if e and e.strip()]


def _nearby_place_ids(session: Session, born_place: Location | None) -> list[int]:
    """`born_place` 自身と、その祖先の場所 id。無ければ空。"""
    if born_place is None:
        return []
    return [node["id"] for node in common_query.place_path(session, born_place.id)]


def _nearby_characters(session: Session, born_place: Location | None, time: Stamp) -> list[Character]:
    """`born_place` かその祖先に、`time` 時点で居る人物・対象。重複回避の材料にする。

    件数は `constants.NEARBY_CHARACTER_LIMIT` まで(祖先をたどるほど無際限に増えるため)。
    """
    place_ids = _nearby_place_ids(session, born_place)
    if not place_ids:
        return []
    ids = session.scalars(common_query.resident_character_ids_select(place_ids, time)).all()
    if not ids:
        return []
    ids = ids[:constants.NEARBY_CHARACTER_LIMIT]
    return list(session.scalars(select(Character).where(Character.id.in_(ids))).all())


def _record_context(records: list[Character]) -> str:
    """人物・対象のリストを、名前(種別)と説明の箇条書きにする。"""
    if not records:
        return "(無し)"
    return "\n".join(f"- {r.name}({r.kind}): {r.text or '(説明なし)'}" for r in records)


def _character_names(characters: list[Character]) -> str:
    """人物・対象のリストを、名前の一覧にする。命名時の重複回避に使う。"""
    if not characters:
        return "(無し)"
    return "、".join(c.name or "" for c in characters)


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
    ai: AIClient, person: bool = True,
) -> Character:
    """**人物(`person=False` なら人物以外の対象)を一件、db へ確定して返す。** ロール判定(当たり外れ)は呼び出し側の責任。"""
    draft = build_character()
    # この場で自動生成される人物・対象は、常にメインキャラクター以外のサブキャラクター扱いにする。
    draft["sub_character"] = True
    if not person:
        for column in _PERSON_ONLY_COLUMNS:
            draft[column] = None

    region_label = _region_label(session, born_place)
    plot_text = _plot_text(session, born_place, time)
    plot_label = plot_text or "(無し)"

    elements = _plot_elements(plot_text, ai)
    chosen_element = rng.choice(elements) if elements else None
    subject = "人物" if person else "対象"
    element_line = (
        f"この{subject}が体現する要素: {chosen_element}\n"
        if chosen_element else ""
    )

    nearby_characters = _nearby_characters(session, born_place, time)
    plot_years = rng.randint(*constants.CHARACTER_PLOT_YEARS_RANGE)
    person_line = (
        f"性別: {draft['sex']} / 体格: {draft['build']} / 口調: {draft['tone']}\n"
        f"性格({'/'.join(PERSONALITY_LEVELS)} の五段階): {_personality_label(draft)}\n"
        if person else ""
    )

    content_prompt = (
        f"出身: {born_place.name if born_place else '不明'}\n"
        f"出身地の特徴:\n{_location_context(born_place)}\n"
        f"地域: {region_label}\n"
        f"{person_line}"
        f"現在の時刻: {time}\n"
        f"この場所・時刻に関連する筋書き:\n{plot_label}\n"
        f"{element_line}"
        f"既にいる人物・対象:\n{_record_context(nearby_characters)}\n"
        f"{plot_span_instruction(plot_years)}\n"
        f"この場所に自然な{subject}を1件、決めてください。"
    )
    if person:
        decided = ai.try_generate_json(
            content_prompt, _CONTENT_SCHEMA, system=_CONTENT_SYSTEM_PROMPT)
    else:
        decided = ai.try_generate_json(
            content_prompt, _NON_PERSON_CONTENT_SCHEMA, system=_NON_PERSON_CONTENT_SYSTEM_PROMPT)
        kind = decided.get("kind")
        draft["kind"] = kind if kind in constants.NON_PERSON_KINDS else rng.choice(constants.NON_PERSON_KINDS)

    draft["text"] = decided.get("text") or draft["text"]
    try:
        age = int(decided.get("age", 0))
    except (TypeError, ValueError):
        age = rng.randint(*constants.GENERATION_CHARACTER_AGE_RANGE)
    age = min(max(age, constants.GENERATION_CHARACTER_AGE_RANGE[0]), constants.GENERATION_CHARACTER_AGE_RANGE[1])

    dead_age = age + rng.randint(10, 100)

    draft["start"] = Stamp(time.year - age)
    draft["end"] = Stamp(time.year - age + dead_age)
    plot_text = (decided.get("plot") or "").strip() or draft["text"]

    # 名前は、説明・年齢・筋書きなど中身が決まったあとに、その内容から連想して決める。
    name_prompt = (
        f"種別: {draft['kind']}\n"
        f"説明: {draft['text']}\n"
        f"年齢: {age}\n"
        f"筋書き: {plot_text}\n"
        f"{person_line}"
        f"居場所: {born_place.name if born_place else '不明'}\n"
        f"場所の特徴:\n{_location_context(born_place)}\n"
        f"所属する地域: {region_label}\n"
        f"既にいる人物・対象の名: {_character_names(nearby_characters)}\n"
        f"この{subject}に似合う名前を決めてください。"
    )
    named = ai.try_generate_json(
        name_prompt, _NAME_SCHEMA,
        system=_NAME_SYSTEM_PROMPT if person else _NON_PERSON_NAME_SYSTEM_PROMPT)
    draft["name"] = named.get("name") or draft["name"]
    draft["text"] = fill_name_placeholder(draft["text"], draft["name"])
    plot_text = fill_name_placeholder(plot_text, draft["name"])

    record = Character(**draft)
    session.add(record)
    session.flush()  # plot/place から character_id で参照するため、先に id を確定する

    if born_place is not None:
        session.add(CharacterPlace(
            character_id=record.id, location_id=born_place.id,
            start=record.start, end=record.end))

    # 生んだ一件には必ず一件、専用の筋書き(CharacterPlot)を添える。
    plot_end = Stamp(time.year + plot_years, time.month, time.day)
    session.add(CharacterPlot(character_id=record.id, text=plot_text, start=time, end=plot_end))

    session.commit()
    when = format_time(time)
    place_label = f"{born_place.name}(id={born_place.id})" if born_place else "不明"
    print(f"[time_keepr/character] {when} 生成: {record.name}"
          f" id={record.id} 種別={record.kind} 出自={place_label} 年齢={age}\n"
          + (f"    性別: {record.sex} / 体格: {record.build} / 口調: {record.tone}\n"
             f"    性格: {_personality_label(record)}\n"
             if person else "")
          + f"    筋書きの要素: {chosen_element or '(無し)'}\n"
          f"    筋書き({plot_years}年、〜{format_time(plot_end)}): {plot_text}\n"
          f"    説明: {record.text or '(説明なし)'}")
    return record


def get_usable_location_q(time: Stamp):
    """`time` の時点で有効なプロットを持ち、居る人物数がまだ許容範囲未満の場所の id。"""

    base_q = (
        select(Location.id)
        .outerjoin(
            CharacterPlace,
            and_(CharacterPlace.location_id == Location.id),
        )
        .outerjoin(
            Character, Character.id == CharacterPlace.character_id
        )
        .outerjoin(
            CharacterPlot, Character.id == CharacterPlot.character_id
        )
        .where(
            location_active_condition(time),
        )
    )

    q_1 = (
        base_q
        .where(
            CharacterPlot.id == None,
        )
    )

    q_2 = (
        base_q
        .where(
            character_plot_time_condition(time)
        )
        .group_by(Location.id)
        .having(
            func.count(CharacterPlot.character_id.distinct()) < constants.MAX_CHARACTER_PLOT_PER_LOCATION
        )
    )

    return union_all(q_1, q_2)


def generate_random(session: Session, time: Stamp, ai: AIClient) -> Character | None:
    """ロールに当たったら、人物か人物以外の対象を一件 db へ確定して返す。当たらなければ None。"""

    usable_location_q = get_usable_location_q(time)
    eligible_places = session.scalars(select(Location).where(Location.id.in_(usable_location_q))).all()
    if not eligible_places:
        print(f"[time_keepr/character] 空きのある場所が無いため見送り")
        return None

    for location in eligible_places:
        try_generate_character(
            session, time, location, ai
        )


def try_generate_character(
    session: Session,
    time: Stamp,
    location: Location,
    ai: AIClient,
):
    if not _should_roll(time):
        return None

    seed = random.randrange(10 ** 9)
    rng = random.Random(seed)
    roll = rng.random()
    when = format_time(time)

    if roll >= constants.GENERATION_CHARACTER_PROBABILITY:
        print(f"[time_keepr/character] {when} 判定: "
              f"seed={seed} roll={roll:.4f} >= {constants.GENERATION_CHARACTER_PROBABILITY} → 見送り")
        return None
    print(f"[time_keepr/character] {when} 判定: "
          f"seed={seed} roll={roll:.4f} < {constants.GENERATION_CHARACTER_PROBABILITY} → 生成")

    # 人物か、人物以外の対象か。数の偏りは AI に任せずサイコロで決める。
    person = rng.random() >= constants.NON_PERSON_PROBABILITY
    print(f"[time_keepr/character] {when} 種別判定: {'人物' if person else '人物以外の対象'}")

    return _generate_one(session, location, time, rng, ai, person=person)
