#!/usr/bin/env python3
"""factory_boy（`factory.alchemy`）で人物（Character）レコード一件分の下書きを組む。

https://factoryboy.readthedocs.io/en/stable/orms.html#module-factory.alchemy

固有名詞（名前・読み）や本文（text）は仮の値で埋めるだけにとどめる。
仕上げは `DEM.claude_interface.main.review_character` に渡し、クロードに
文脈へ合わせて補完・調整させる想定（そこまでがこのモジュールの外）。

既存レコードを指す欄（`root_place_name` `kind_id` `born_place_id`
`belong_id`）は、ここでは作らない。存在しない id を持たせないよう、
呼び出し側が `novel.py` 経由で引いた実在の id を渡す。

factory_boy の `SQLAlchemyModelFactory` では、`build()` は session に一切触れない
（ただの Python オブジェクト構築で終わる）。db への flush は `create()` の側の
仕事で、そこを **`sqlalchemy_session_persistence = "flush"` で止め、commit しない**
のがこのモジュールの境界。Claude のレビューを経る前に確定させないための境界。
"""
from __future__ import annotations

import factory
from factory.alchemy import SQLAlchemyModelFactory

from DEM.db.schema import Character, get_session

_SEX_CHOICES = ("男", "女", "不定")
_BUILD_CHOICES = ("細身", "小柄", "がっしり", "長身", "ふくよか", "痩身")
_TONE_CHOICES = ("丁寧", "ぶっきらぼう", "早口", "のんびり", "無口", "高圧的")
_FIRST_PERSON_CHOICES = ("わたし", "俺", "僕", "あたし", "自分", "うち")
_SECOND_PERSON_CHOICES = ("あなた", "君", "お前", "そちら", "あんた")
_THIRD_PERSON_CHOICES = ("さん", "くん", "ちゃん", "殿", "氏")

# 性格の 12 軸。schema.py の Character に合わせる。
_PERSONALITY_RANGE = (-5, 5)


class CharacterFactory(SQLAlchemyModelFactory):
    """人物レコード一件分の下書きを組む。

    `sqlalchemy_session_persistence = "flush"` なので、`create()` した
    時点では db に flush されるだけで commit はしない（`build()` は session に
    触れないため、ここでは使わない）。呼び出し側が中身を見て補完・調整した
    あと、commit する。
    """

    class Meta:
        model = Character
        sqlalchemy_session_factory = get_session
        sqlalchemy_session_persistence = "flush"
        # `build` は Character の列名（体格）と `Factory.build()` が衝突するので、
        # 下の `build_` で宣言して schema 側の `build` へ流し込む。
        rename = {"build_": "build"}

    name = factory.Sequence(lambda n: f"仮名{n}")
    read = ""
    text = ""

    sex = factory.Faker("random_element", elements=_SEX_CHOICES)
    height = factory.Faker("pyfloat", min_value=140, max_value=195, right_digits=1, positive=True)
    build_ = factory.Faker("random_element", elements=_BUILD_CHOICES)

    first_person = factory.Faker("random_element", elements=_FIRST_PERSON_CHOICES)
    second_person = factory.Faker("random_element", elements=_SECOND_PERSON_CHOICES)
    third_person = factory.Faker("random_element", elements=_THIRD_PERSON_CHOICES)
    tone = factory.Faker("random_element", elements=_TONE_CHOICES)

    sincerity = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    curiosity = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    proactivity = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    cooperativeness = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    sociability = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    emotional_expression = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    self_esteem = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    self_efficacy = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    stress_resilience = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    flexibility_of_values = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    sensitivity = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])
    imagination = factory.Faker("random_int", min=_PERSONALITY_RANGE[0], max=_PERSONALITY_RANGE[1])

    world_influence = factory.Faker("random_int", min=0, max=2)

    # 実在レコードを指す欄。呼び出し側が上書きする前提で None のまま。
    root_place_name = None
    kind_id = None
    born_place_id = None
    belong_id = None
    start = None
    end = None


def build_character(**overrides) -> Character:
    """`CharacterFactory.create` の薄いラッパー。db へは flush までで commit しない。

    （`Meta.sqlalchemy_session_persistence = "flush"` により、`create()` を
    呼んでも commit までは進まない。`build()` は session に触れず flush されない
    ため使わない。）
    """
    return CharacterFactory.create(**overrides)
