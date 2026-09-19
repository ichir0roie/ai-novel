#!/usr/bin/env python3
"""factory_boy でランダムな出来事（Event）一件分の下書きを**辞書**として組む。

db には一切触れない。`DEM.db.schema.Event` にも依存しない（列名を合わせて
いるだけ）。固有名詞（`name`）や本文（`text`）は仮の値で埋めるだけにとどめる。
実在レコードを指す欄（`place_id` `character_id` `object_id`
`parent_event_id`）と時刻（`time` `start` `end`）はここでは埋めない——
存在確認や db への書き込みは呼び出し側
（`DEM.claude_interface.randomizer.commit_event`）の仕事。
"""
from __future__ import annotations

import factory

_KIND_CHOICES = ("", "関係", "火種", "指標", "争点")


class EventFactory(factory.DictFactory):
    """出来事レコード一件分の下書きを、db に触れずに辞書として組む。"""

    name = factory.Sequence(lambda n: f"仮の出来事{n}")
    kind = factory.Faker("random_element", elements=_KIND_CHOICES)
    text = ""

    # 実在レコードを指す欄・時刻。呼び出し側が上書きする前提で None のまま。
    time = None
    parent_event_id = None
    place_id = None
    character_id = None
    object_id = None
    start = None
    end = None


def build_event(**overrides) -> dict:
    """`EventFactory.build` の薄いラッパー。db には一切触れない。"""
    return EventFactory.build(**overrides)
