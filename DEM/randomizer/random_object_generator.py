#!/usr/bin/env python3
"""ランダムな個体(Object)一件分の下書きを辞書として組む。db には触れない。"""
from __future__ import annotations

import factory

_INFLUENCE_RANGE = (0, 3)


class ObjectFactory(factory.DictFactory):
    name = factory.Sequence(lambda n: f"仮の群{n}")
    read = ""
    text = ""

    world_influence = factory.Faker(
        "random_int", min=_INFLUENCE_RANGE[0], max=_INFLUENCE_RANGE[1])

    root_place_name = None
    start = None
    end = None


def build_object(**overrides) -> dict:
    return ObjectFactory.build(**overrides)
