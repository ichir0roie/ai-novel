#!/usr/bin/env python3
"""ランダムな人物(Character)一件分の下書きを辞書として組む。db には触れない。"""
from __future__ import annotations

import factory

from DEM.db.schema import CHARACTER_KIND_PERSON

_SEX_CHOICES = ("男", "女", "不定")
_BUILD_CHOICES = ("細身", "小柄", "がっしり", "長身", "ふくよか", "痩身")
_TONE_CHOICES = ("丁寧", "ぶっきらぼう", "早口", "のんびり", "無口", "高圧的")
_FIRST_PERSON_CHOICES = ("わたし", "俺", "僕", "あたし", "自分", "うち")
_SECOND_PERSON_CHOICES = ("あなた", "君", "お前", "そちら", "あんた")
_THIRD_PERSON_CHOICES = ("さん", "くん", "ちゃん", "殿", "氏")

# 性格の 12 軸。schema.py の Character に合わせる。
_PERSONALITY_RANGE = (-5, 5)


class CharacterFactory(factory.DictFactory):
    class Meta:
        # `build` は Character の列名(体格)と `Factory.build()` が衝突するので、
        # 下の `build_` で宣言して辞書の `build` キーへ流し込む。
        rename = {"build_": "build"}

    name = factory.Sequence(lambda n: f"仮名{n}")
    read = ""
    text = ""
    kind = CHARACTER_KIND_PERSON

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

    start = None
    end = None


def build_character(**overrides) -> dict:
    return CharacterFactory.build(**overrides)
