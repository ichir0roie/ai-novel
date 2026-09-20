#!/usr/bin/env python3
"""**世界の側の人物を、時の流れの中で自動的に増やす。**

`DEM.local_ai.time_keepr.main` の常駐ループから毎日呼ばれる。二つの経路がある。

- `generate_random`: 「1月に一度、月初に、10%の確率で」場所を一つだけ選び、
  人物を一件生む(既存の経路)。**確率が低いうえに場所も一件しか選ばないため、
  何百年ぶん回しても特定の地域に複数の人物が生まれないことがある**(長期間、
  一つの地域に複数のキャラが生まれない問題)
- `seed_initial_characters`: `Location.random_character_source` がオンで、
  まだ誰も人物が居ない場所へ、月初のたびに 1〜4 人をまとめて生む。場所を
  「まとめて人が住む場所」として明示的に選べるようにすることで、上の細い
  トリクルに頼らずその場所へ確実に顔ぶれを揃える。一度生まれれば
  (`born_place_id` を持つ人物が一人でも居れば)その場所は対象から外れるので、
  何度呼んでも増え続けることはない

どちらも `claude を介さず db への確定まで一度に行う。名前・読み・口調・出自・
年齢といった AI の判断が要る欄だけをローカルAI(`ai_client`)に委ねる。
判断の材料として、場所の `text` と参考カラム(`sample_region` `sample_culture`
`sample_era`)、所属する地域、その場所・時刻に関連する筋書き
(`load_location_plot` で出自の場所とその祖先をたどって集める)を渡し、
返ってきた内容から情動(`CharacterDrive`)も一件確定する。能力・特徴は
表に分けず、`text`(人物説明)の中に書き込む。
"""
from __future__ import annotations

import random

from DEM.ai_instructions.naming import CHARACTER_NAMING_INSTRUCTION
from DEM.data_access_logic.query import story_createion_query, world_createion_query
from DEM.db.schema import (
    Character, CharacterDrive, Location, Session,
    Stamp,
)
from DEM.local_ai import ai_client
from DEM.local_ai.time_keeper._format import format_time
from DEM.randomizer.random_character_generator import build_character

PROBABILITY = 0.1  # 1月に1度、10%の確率で

# `random_character_source` がオンの場所にまとめて生む人数の幅。
SEED_COUNT_RANGE = (1, 4)

# 生成時点での年齢の幅。0(赤子)ではなく、この範囲でランダムに選んだ年数だけ
# 過去に生まれたことにする(`character_lifespan._NATURAL_DEATH_MIN_AGE` の
# 50 歳より十分若い範囲に収め、生成直後に老衰死しないようにする)。
_AGE_RANGE = (0, 40)

# 情動の強さの幅。`CharacterDrive.level` に合わせる。
_EMOTION_LEVEL_RANGE = (1, 5)

_SYSTEM_PROMPT = (
    "あなたは架空の世界観を構築する設定作家です。"
    "新しく生まれる人物1件について、名前・読み・簡単な人物説明・年齢・"
    "情動を、自然な固有名詞で JSON で答えてください。"
    + CHARACTER_NAMING_INSTRUCTION +
    f"年齢(age)は{_AGE_RANGE[0]}〜{_AGE_RANGE[1]}歳の範囲で、"
    "text の人物説明と矛盾しないように、あなた自身で決めてください"
    "(例えば老成した説明なら年長めに、幼さの残る説明なら年少めに)。"
    "この人物が目立った能力・特技を持つのが自然なら、その内容を text の"
    "人物説明の中に地の文として書き込んでください(能力を別項目には分けない)。"
    "情動(emotion)は、この人物を特徴づける信念・目標・意図を一言〜二言で、"
    "その強さ(emotion_level)を1〜5の整数で決めてください。"
    "渡す場所の説明・参考地域・参考文化・参考時代や、所属する地域、"
    "その場所・時刻に関連する筋書きに、この人物の生活・仕事・性格が"
    "自然に馴染むよう考慮してください(参考地域・参考文化・参考時代は、"
    "固有名詞をそのまま持ち込むのではなく、地理・気候・生業・価値観の"
    "手がかりとして使ってください)。"
    "キーは name(名前), read(読み), text(具体的な生活・仕事・関係が伝わる"
    "2〜3文の人物説明。能力・特技があれば含む。「優しい」「謎めいた」の"
    "ような、誰にでも当てはまる抽象的な形容だけで済ませず、この人物固有の"
    "具体的な癖・関わり・生い立ちを最低一つ含める), age(年齢, 整数), "
    "emotion(情動), emotion_level(情動の強さ, 整数)の五つだけ。"
)


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
    draft = build_character(
        born_place_id=born_place.id if born_place else None,
    )

    region_label = _region_label(session, born_place)
    plot_texts = _plot_texts(session, born_place, time)
    plot_label = "\n".join(f"- {text}" for text in plot_texts) or "(無し)"

    prompt = (
        f"生まれの場所: {born_place.name if born_place else '不明'}\n"
        f"場所の特徴:\n{_location_context(born_place)}\n"
        f"所属する地域: {region_label}\n"
        f"性別: {draft['sex']} / 体格: {draft['build']} / 口調: {draft['tone']}\n"
        f"現在の時刻: {time}\n"
        f"年齢は{_AGE_RANGE[0]}〜{_AGE_RANGE[1]}歳の範囲で、text の人物説明に"
        "似合う歳を選んでください。\n"
        f"この場所・時刻に関連する筋書き:\n{plot_label}\n"
        "この場所に自然な人物を1件、決めてください。"
    )
    decided = ai_client.try_generate_json(prompt, system=_SYSTEM_PROMPT)

    draft["name"] = decided.get("name") or draft["name"]
    draft["read"] = decided.get("read") or draft["read"]
    draft["text"] = decided.get("text") or draft["text"]
    try:
        age = int(decided.get("age"))
    except (TypeError, ValueError):
        age = rng.randint(*_AGE_RANGE)
    age = min(max(age, _AGE_RANGE[0]), _AGE_RANGE[1])
    draft["start"] = Stamp(time.year - age)

    record = Character(**draft)
    session.add(record)
    session.flush()  # emotion から character_id で参照するため、先に id を確定する

    emotion_label = "(なし)"
    emotion_text = (decided.get("emotion") or "").strip()
    if emotion_text:
        try:
            emotion_level = int(decided.get("emotion_level"))
        except (TypeError, ValueError):
            emotion_level = rng.randint(*_EMOTION_LEVEL_RANGE)
        emotion_level = min(max(emotion_level, _EMOTION_LEVEL_RANGE[0]), _EMOTION_LEVEL_RANGE[1])
        session.add(CharacterDrive(
            character_id=record.id, text=emotion_text, level=emotion_level, start=time))
        emotion_label = f"{emotion_text}(level={emotion_level})"

    session.commit()
    when = format_time(time)
    place_label = f"{born_place.name}(id={born_place.id})" if born_place else "不明"
    print(f"[time_keepr/character] {when} 生成: {record.name}({record.read})"
          f" id={record.id} 出自={place_label} 年齢={age}\n"
          f"    性別: {record.sex} / 体格: {record.build} / 口調: {record.tone}\n"
          f"    情動: {emotion_label}\n"
          f"    説明: {record.text or '(説明なし)'}")
    return record


def generate_random(session: Session, time: Stamp) -> Character | None:
    """ロールに当たったら、人物を一件 db へ確定して返す。当たらなければ None。"""
    if not _should_roll(time):
        return None

    seed = random.randrange(10 ** 9)
    rng = random.Random(seed)
    roll = rng.random()
    when = format_time(time)
    if roll >= PROBABILITY:
        print(f"[time_keepr/character] {when} 月初判定: "
              f"seed={seed} roll={roll:.4f} >= {PROBABILITY} → 見送り")
        return None
    print(f"[time_keepr/character] {when} 月初判定: "
          f"seed={seed} roll={roll:.4f} < {PROBABILITY} → 生成")

    # born_place も、この時刻にまだ存在している場所だけを候補にする。
    places = session.scalars(
        world_createion_query.alive_locations_select(time)).all()
    # 出自の人物が既に上限に達している場所は選ばない。
    eligible_places = [
        p for p in places
        if int(session.scalar(world_createion_query.character_count_at_place_select(p.id)) or 0)
        < world_createion_query.MAX_PER_LOCATION
    ]
    if places and not eligible_places:
        print(f"[time_keepr/character] {when} 空きのある場所が無いため見送り")
        return None
    born_place = rng.choice(eligible_places) if eligible_places else None

    return _generate_one(session, born_place, time, rng)


def seed_initial_characters(session: Session, time: Stamp) -> list[Character]:
    """**`random_character_source` がオンで、まだ誰も居ない場所へ、まとめて人物を生む。**

    月初のたびに対象を見るが、対象は「フラグがオンなのに、まだ `born_place_id`
    を持つ人物が一人も居ない場所」だけなので、一度生めば同じ場所は次の月には
    もう対象から外れる(場所ごとに一度きり)。`generate_random` の月一件だけの
    細いトリクルと違い、その場所へ確実に複数人をまとめて配置する。
    """
    if not _should_roll(time):
        return []

    places = session.scalars(
        world_createion_query.flagged_character_source_locations_select(time)).all()
    unseeded_places = [
        p for p in places
        if int(session.scalar(world_createion_query.character_count_at_place_select(p.id)) or 0) == 0
    ]
    if not unseeded_places:
        return []

    when = format_time(time)
    created: list[Character] = []
    for place in unseeded_places:
        seed = random.randrange(10 ** 9)
        rng = random.Random(seed)
        count = rng.randint(*SEED_COUNT_RANGE)
        print(f"[time_keepr/character] {when} 初回生成: {place.name}(id={place.id}) "
              f"seed={seed} {count}人をまとめて生成")
        for _ in range(count):
            created.append(_generate_one(session, place, time, rng))

    return created
