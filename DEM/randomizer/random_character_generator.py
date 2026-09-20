#!/usr/bin/env python3
"""factory_boy でランダムな人物(Character)一件分の下書きを**辞書**として組む。

https://factoryboy.readthedocs.io/en/stable/reference.html#factory.DictFactory

db には一切触れない。`DEM.db.schema.Character` にも依存しない
(列名を合わせているだけで、import はしていない)。固有名詞(名前・読み)や
本文(text)は仮の値で埋めるだけにとどめる。実在レコードを指す欄
(`root_place_name` `kind_id` `born_place_id` `belong_id`)もここでは
埋めない——存在確認や db への書き込みは呼び出し側
(`DEM.claude_interface.randomizer.commit_character`)の仕事。
"""
from __future__ import annotations

import factory

_SEX_CHOICES = ("男", "女", "不定")
_BUILD_CHOICES = ("細身", "小柄", "がっしり", "長身", "ふくよか", "痩身")
_TONE_CHOICES = ("丁寧", "ぶっきらぼう", "早口", "のんびり", "無口", "高圧的")
_FIRST_PERSON_CHOICES = ("わたし", "俺", "僕", "あたし", "自分", "うち")
_SECOND_PERSON_CHOICES = ("あなた", "君", "お前", "そちら", "あんた")
_THIRD_PERSON_CHOICES = ("さん", "くん", "ちゃん", "殿", "氏")

# 性格の 12 軸。schema.py の Character に合わせる。
_PERSONALITY_RANGE = (-5, 5)


class CharacterFactory(factory.DictFactory):
    """人物レコード一件分の下書きを、db に触れずに辞書として組む。"""

    class Meta:
        # `build` は Character の列名(体格)と `Factory.build()` が衝突するので、
        # 下の `build_` で宣言して辞書の `build` キーへ流し込む。
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


def build_character(**overrides) -> dict:
    """`CharacterFactory.build` の薄いラッパー。db には一切触れない。"""
    return CharacterFactory.build(**overrides)
