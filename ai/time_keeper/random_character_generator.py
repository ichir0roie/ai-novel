#!/usr/bin/env python3
from __future__ import annotations

import random

from sqlalchemy import and_, func, select, union, union_all
from sqlalchemy.orm import aliased

from ai.instructions.naming import (
    CHARACTER_NAMING_INSTRUCTION, NAME_PLACEHOLDER, IDEA_NAMING_INSTRUCTION,
    fill_name_placeholder,
)
from data_access_logic.query import common_query, story_createion_query, world_createion_query
from data_access_logic.query.base import *
from db.schema import *
from db.schema import PERSON_PARAMETER_COLUMNS, PERSONALITY_COLUMNS, PERSONALITY_LEVELS
from db.child_lists import load_children
from ai.time_keeper._ai import AIClient
from ai.time_keeper import constants, idea_context, meme
from ai.time_keeper._format import format_time
from randomizer.random_character_generator import build_character

_PLACEHOLDER_INSTRUCTION = (
    f"この一件の名前はまだ決まっていない。text の中でこの一件を指すときは必ず「{NAME_PLACEHOLDER}」と書き、名前を考案して書き込まない。"
)

_AGE_RANGE = f"{constants.GENERATION_CHARACTER_AGE_RANGE[0]}〜{constants.GENERATION_CHARACTER_AGE_RANGE[1]}"


def _meme_instruction(subject: str) -> str:
    return (
        f"「この{subject}の行動原理(ミーム)」が渡されているときは、それぞれに振られた古今表裏({meme.position_legend()})を変えずに、"
        f"ミームどうしの関係を整理して principle に書いてください。何を経て古いものを手放したか、表と裏がどう食い違い、"
        f"この{subject}の中でどう折り合っているかを、出来事や人との関わりとして書く。食い違うミームも、どちらかを捨てずに両方を生かす。"
        f"ミームの文面をそのまま書き写さない。text もこの整理と矛盾させない。"
    )


_CONTENT_SYSTEM_PROMPT = f"""\
あなたは架空の世界観を構築する設定作家です。
新しく生まれる人物1件について、人物説明・年齢を、自然な日本語で JSON で答えてください。
渡す場所の説明・参考地域・参考文化・参考時代や、所属する地域、その場所・時刻に関連する筋書きに、この人物の生活・仕事・性格が自然に馴染むよう考慮してください(参考地域・参考文化・参考時代は、固有名詞をそのまま持ち込むのではなく、地理・気候・生業・価値観の手がかりとして使ってください)。
「この人物が体現する要素」が渡されているときは、複数の立場のうちあなたが選びやすいものへ寄せず、渡された要素をこの人物の生き方の核として必ず反映してください。
「既にいる人物・対象」が渡されているときは、その役割・関係・特徴とは重ならない人物にしてください(同じ立場・同じ能力・同じ関係性の作り直しをしない)。
「性格」は各軸を {'/'.join(PERSONALITY_LEVELS)} の五段階で渡す(サイコロで決まっていて変えられない)。人物説明はこの段階と矛盾しないようにし、「無」「必」の軸はその極端さが生活・仕事・人との関わり方に具体的な癖として表れるように書く。段階の語をそのまま書き写さない。
{_meme_instruction("人物")}
{_PLACEHOLDER_INSTRUCTION}
キーは次の五つだけ。
- text: 具体的な生活・仕事・関係が伝わる2〜3文の人物説明。目立った能力・特技があれば地の文として含め、別項目には分けない。「優しい」「謎めいた」のような、誰にでも当てはまる抽象的な形容だけで済ませず、この人物固有の具体的な癖・関わり・生い立ちを最低一つ含める。
- age: 年齢(整数)。{_AGE_RANGE}の範囲で、text の人物説明と矛盾しない値をあなた自身で決める。例えば老成した説明なら年長めに、幼さの残る説明なら年少めに。
- principle: 行動原理(ミーム)どうしの関係を整理した2〜4文。ミームが渡されていなければ空文字。
- dialect: 方言。出身地・参考地域・参考文化・生業・生い立ち・年齢・性格・口調から、この人物がどんな言葉で話すかを1〜2文で決める。土地の言葉で話すなら、どの地方風の方言か(現実の方言を手本にしてよい)と、特徴的な語尾・言い回しを一つ以上。標準語で話すなら、その人物らしい癖(語尾・口ぐせ・言い淀み・訛りの名残など)を一つ以上。誰にでも当てはまる「普通の話し方」で済ませない。
- history: 来歴。生まれてから現在(age の歳)までの節目を、歳の順に3〜5件。各要素は age(その時の歳。0 以上、上の age 以下の整数)と text(その歳に何があり、立場・仕事・住まい・人間関係がどう変わったかの1文)。人物説明の立場・仕事・住まいには、いつそうなったかの節目を必ず含める。最後の一件は現在(age の歳)の暮らしにする。"""

_CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "age": {"type": "integer", "minimum": constants.GENERATION_CHARACTER_AGE_RANGE[0], "maximum": constants.GENERATION_CHARACTER_AGE_RANGE[1]},
        "principle": {"type": "string"},
        "dialect": {"type": "string"},
        "history": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "age": {"type": "integer", "minimum": 0,
                            "maximum": constants.GENERATION_CHARACTER_AGE_RANGE[1]},
                    "text": {"type": "string"},
                },
                "required": ["age", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["text", "age", "principle", "dialect", "history"],
    "additionalProperties": False,
}

_NON_PERSON_CONTENT_SYSTEM_PROMPT = f"""\
あなたは架空の世界観を構築する設定作家です。
ある場所と、そこに居る人物・既にある対象を渡すので、この場所を拠り所に生まれる人物以外の対象(国・組織・商会・氏族・集団など、まとまりとして動くもの。あるいは物)を1件だけ考え、JSON で答えてください。
渡す場所の産業・地形・人間関係のうち少なくとも一つを具体的に使う。
「この対象が体現する要素」が渡されているときは、渡された要素をこの対象の成り立ちの核として必ず反映してください。
既にある対象と役割が重なるものは作らない。
{_meme_instruction("対象")}
{_PLACEHOLDER_INSTRUCTION}
キーは次の四つだけ。
- kind: 種別。{' / '.join(constants.NON_PERSON_KINDS)} のいずれか一つ。
- text: この対象が何であって、何を決められて、誰に対して力を持つのかが伝わる2〜3文の説明。「由緒ある」「謎めいた」のような、どの対象にも当てはまる形容だけで済ませない。
- age: 成り立ってからの年数(整数)。{_AGE_RANGE}の範囲。
- principle: 行動原理(ミーム)どうしの関係を整理した2〜4文。ミームが渡されていなければ空文字。"""

_NON_PERSON_CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": list(constants.NON_PERSON_KINDS)},
        "text": {"type": "string"},
        "age": {"type": "integer", "minimum": constants.GENERATION_CHARACTER_AGE_RANGE[0], "maximum": constants.GENERATION_CHARACTER_AGE_RANGE[1]},
        "principle": {"type": "string"},
    },
    "required": ["kind", "text", "age", "principle"],
    "additionalProperties": False,
}

_NAME_SYSTEM_PROMPT = f"""\
あなたは架空の世界観を構築する設定作家です。
内容が決まっている人物1件に、名前と名字を付けます。
{CHARACTER_NAMING_INSTRUCTION}
渡す人物説明・年齢・体格や口調から連想できる、この人物に似合う名前にしてください。
居場所・場所の特徴・所属する地域が渡されているときは、その参考地域・参考文化・参考時代を名の響きや漢字・カタカナの選び方の手がかりにして、同じ場所の人物として馴染む名にしてください(固有名詞をそのまま持ち込まない)。
名字は、生まれたときに名乗るものを、出身地・身分・家業・参考文化から決める。その土地・身分で名字を持たないのが自然なら空文字にする。
キーは name(名字を含めない名)と family_name(名字)の二つ。"""

_NON_PERSON_NAME_SYSTEM_PROMPT = f"""\
あなたは架空の世界観を構築する設定作家です。
内容が決まっている人物以外の対象(国・組織・集団・物など)1件に、名前だけを付けます。
{IDEA_NAMING_INSTRUCTION}
組織の名は場所名か役割名で呼べる形にする。
居場所・場所の特徴・所属する地域が渡されているときは、その参考地域・参考文化・参考時代を名の響きや漢字・カタカナの選び方の手がかりにして、同じ場所のものとして馴染む名にしてください(固有名詞をそのまま持ち込まない)。
「既にいる人物・対象の名」が渡されているときは、それらと紛らわしい名にしない。
キーは name(名前)だけ。"""

_POLISH_SYSTEM_PROMPT = f"""\
あなたは架空の世界観を構築する設定作家です。
決まったばかりの人物・対象の説明(下書き)と、その下書きに関係する設定を渡すので、設定を踏まえて説明を清書してください。
下書きの人物像・生い立ち・関係・長さは変えない。設定と食い違うところ、設定を踏まえると具体的にできるところだけを直す。
{_PLACEHOLDER_INSTRUCTION}
キーは text(清書した説明)だけ。"""

_POLISH_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}

_NAME_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
    },
    "required": ["name"],
    "additionalProperties": False,
}

_PERSON_NAME_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "family_name": {"type": "string"},
    },
    "required": ["name", "family_name"],
    "additionalProperties": False,
}

def history_section(items, born_year: int, age: int) -> str:
    """来歴の各行に年と歳を併記する。最後の行は現在の歳にそろえ、後から読む側がその時点の段階を引けるようにする。"""
    rows = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or "").strip()
        try:
            at = int(item.get("age"))
        except (TypeError, ValueError):
            continue
        if text and 0 <= at <= age:
            rows.append((at, text))
    rows.sort(key=lambda row: row[0])
    if rows and rows[-1][0] == age:
        rows[-1] = (age, f"現在。{rows[-1][1]}")
    else:
        rows.append((age, "現在。"))
    return "\n".join(f"- {born_year + at}年({at}歳): {text}" for at, text in rows)


def _should_roll(time: Stamp) -> bool:
    return time.day == 1


def _personality_label(values) -> str:
    get = values.get if hasattr(values, "get") else (lambda column: getattr(values, column))
    columns = CharacterParameter.__table__.columns
    return " / ".join(f"{columns[column].comment}={get(column)}" for column in PERSONALITY_COLUMNS)


def _region_label(session: Session, born_place: Location | None) -> str:
    if born_place is None or born_place.parent_id is None:
        return "不明"
    parent = session.get(Location, born_place.parent_id)
    if parent is None:
        return "不明"
    return f"{parent.name}({parent.kind})"


def _story_text(session: Session, born_place: Location | None, time: Stamp) -> str:
    if born_place is None:
        return ""
    return story_createion_query.load_location_story_text(session, born_place.id, time)


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


def _story_elements(story_text: str, ai: AIClient) -> list[str]:
    """抜き出し(この関数)と選択(呼び出し側の `rng.choice`)を分けることで、
    複数の立場を持つ筋書きでも生成のたびランダムに割り振られるようにし、
    モデルが生成時に自由選択して同じ立場へ偏るのを防ぐ。
    """
    if not story_text:
        return []
    decided = ai.try_generate_json(
        story_text, _ELEMENT_SCHEMA, system=_ELEMENT_SYSTEM_PROMPT)
    return [e.strip() for e in decided.get("elements", []) if e and e.strip()]


def _nearby_place_ids(session: Session, born_place: Location | None) -> list[int]:
    if born_place is None:
        return []
    return [node["id"] for node in common_query.place_path(session, born_place.id)]


def _nearby_characters(session: Session, born_place: Location | None, time: Stamp) -> list[Character]:
    """件数は `constants.NEARBY_CHARACTER_LIMIT` まで(祖先をたどるほど無際限に増えるため)。"""
    place_ids = _nearby_place_ids(session, born_place)
    if not place_ids:
        return []
    ids = session.scalars(common_query.resident_character_ids_select(place_ids, time)).all()
    if not ids:
        return []
    ids = ids[:constants.NEARBY_CHARACTER_LIMIT]
    return list(session.scalars(select(Character).where(Character.id.in_(ids))).all())


def _record_context(records: list[Character]) -> str:
    if not records:
        return "(無し)"
    return "\n".join(f"- {r.name}({r.kind}): {r.text or '(説明なし)'}" for r in records)


def _character_names(characters: list[Character]) -> str:
    if not characters:
        return "(無し)"
    return "、".join(c.name or "" for c in characters)


def _location_context(place: Location | None) -> str:
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
    draft = build_character()
    # 生まれた時点で決める値なので、期間を限らない一行だけを持つ
    parameters = draft["parameters"][0]
    if not person:
        for column in PERSON_PARAMETER_COLUMNS:
            parameters[column] = None

    region_label = _region_label(session, born_place)
    story_text = _story_text(session, born_place, time)
    story_label = story_text or "(無し)"

    elements = _story_elements(story_text, ai)
    chosen_element = rng.choice(elements) if elements else None
    subject = "人物" if person else "対象"
    element_line = (
        f"この{subject}が体現する要素: {chosen_element}\n"
        if chosen_element else ""
    )

    drawn_memes = meme.draw(
        session, rng, constants.MEME_PERSON_CATEGORIES if person else constants.MEME_NON_PERSON_CATEGORIES)
    meme_line = (
        f"この{subject}の行動原理(ミーム。{meme.position_legend()}):\n{meme.meme_section(drawn_memes)}\n"
        if drawn_memes else ""
    )

    nearby_characters = _nearby_characters(session, born_place, time)
    person_line = (
        f"性別: {parameters['sex']} / 体格: {parameters['build']} / 口調: {parameters['tone']}\n"
        f"性格({'/'.join(PERSONALITY_LEVELS)} の五段階): {_personality_label(parameters)}\n"
        if person else ""
    )

    content_prompt = (
        f"出身: {born_place.name if born_place else '不明'}\n"
        f"出身地の特徴:\n{_location_context(born_place)}\n"
        f"地域: {region_label}\n"
        f"{person_line}"
        f"現在の時刻: {time}\n"
        f"この場所・時刻に関連する筋書き:\n{story_label}\n"
        f"{element_line}"
        f"{meme_line}"
        f"既にいる人物・対象:\n{_record_context(nearby_characters)}\n"
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
    if person:
        parameters["dialect"] = (decided.get("dialect") or "").strip() or None
    context = idea_context.gather(session, draft["text"], ai, born_place.id if born_place else None, time)
    if context.related:
        polished = ai.try_generate_json(
            f"下書き: {draft['text']}\n{idea_context.prompt_section(context.related, context.called)}この説明を清書してください。",
            _POLISH_SCHEMA, system=_POLISH_SYSTEM_PROMPT, timeout=constants.IDEA_POLISH_TIMEOUT)
        draft["text"] = (polished.get("text") or "").strip() or draft["text"]
    try:
        age = int(decided.get("age", 0))
    except (TypeError, ValueError):
        age = rng.randint(*constants.GENERATION_CHARACTER_AGE_RANGE)
    age = min(max(age, constants.GENERATION_CHARACTER_AGE_RANGE[0]), constants.GENERATION_CHARACTER_AGE_RANGE[1])

    if person:
        draft["text"] += f"\n\n# 来歴\n{history_section(decided.get('history'), time.year - age, age)}"
    if drawn_memes:
        draft["text"] += f"\n\n# meme\n{meme.meme_section(drawn_memes)}"
        principle = (decided.get("principle") or "").strip()
        if principle:
            draft["text"] += f"\n\n# 行動原理\n{principle}"

    dead_age = age + rng.randint(10, 100)

    draft["start"] = Stamp(time.year - age)
    draft["end"] = Stamp(time.year - age + dead_age)

    dialect_line = f"方言: {parameters['dialect']}\n" if person and parameters.get("dialect") else ""
    # 名前は、説明・年齢など中身が決まったあとに、その内容から連想して決める。
    name_prompt = (
        f"種別: {draft['kind']}\n"
        f"説明: {draft['text']}\n"
        f"年齢: {age}\n"
        f"{person_line}"
        f"{dialect_line}"
        f"居場所: {born_place.name if born_place else '不明'}\n"
        f"場所の特徴:\n{_location_context(born_place)}\n"
        f"所属する地域: {region_label}\n"
        f"既にいる人物・対象の名: {_character_names(nearby_characters)}\n"
        f"この{subject}に似合う名前を決めてください。"
    )
    if person:
        named = ai.try_generate_json(name_prompt, _PERSON_NAME_SCHEMA, system=_NAME_SYSTEM_PROMPT)
        parameters["family_name"] = (named.get("family_name") or "").strip() or None
    else:
        named = ai.try_generate_json(name_prompt, _NAME_SCHEMA, system=_NON_PERSON_NAME_SYSTEM_PROMPT)
    draft["name"] = named.get("name") or draft["name"]
    draft["text"] = fill_name_placeholder(draft["text"], draft["name"])

    record = Character(**{key: value for key, value in draft.items() if key != "parameters"})
    load_children(record, "parameters", draft["parameters"])
    session.add(record)
    session.flush()  # place から character_id で参照するため、先に id を確定する

    if born_place is not None:
        session.add(CharacterPlace(
            character_id=record.id, location_id=born_place.id,
            start=record.start, end=record.end))
    idea_context.link(session, record, context.linked)

    session.commit()
    when = format_time(time)
    place_label = f"{born_place.name}(id={born_place.id})" if born_place else "不明"
    print(f"[time_keepr/character] {when} 生成: {record.name}"
          f" id={record.id} 種別={record.kind} 出自={place_label} 年齢={age}\n"
          + (f"    名字: {parameters['family_name'] or '(無し)'}\n"
             f"    性別: {parameters['sex']} / 体格: {parameters['build']} / 口調: {parameters['tone']}\n"
             f"    方言: {parameters['dialect']}\n"
             f"    性格: {_personality_label(parameters)}\n"
             if person else "")
          + f"    筋書きの要素: {chosen_element or '(無し)'}\n"
          + "".join(f"    ミーム: {item['position']}: {item['text']}\n" for item in drawn_memes)
          + f"    説明: {record.text or '(説明なし)'}")
    return record


def get_usable_location_q(time: Stamp):
    base_q = (
        select(Location.id)
        .outerjoin(
            CharacterPlace,
            and_(CharacterPlace.location_id == Location.id),
        )
        .outerjoin(
            Character, Character.id == CharacterPlace.character_id
        )
        .where(
            location_active_condition(time),
        )
    )

    q_1 = (
        base_q
        .where(
            Character.id == None,
        )
    )

    q_2 = (
        base_q
        .where(
            character_time_condition(time)
        )
        .group_by(Location.id)
        .having(
            func.count(Character.id.distinct()) < constants.MAX_CHARACTER_PER_LOCATION
        )
    )

    return union_all(q_1, q_2)


def generate_random(session: Session, time: Stamp, ai: AIClient) -> Character | None:
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
