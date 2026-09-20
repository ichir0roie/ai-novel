#!/usr/bin/env python3
"""factory_boy でランダムな場所の資源(LocationResource)一件分の下書きを**辞書**として組む。

db には一切触れない。`DEM.db.schema.LocationResource` にも依存しない(列名を
合わせているだけで、import はしていない)。`DEM/randomizer/random_location_generator.py`
と同じ立ち位置: 判断が要る中身(種別・量・尽きるまでの年数)は呼び出し側が埋める。
"""
from __future__ import annotations

import factory


class LocationResourceFactory(factory.DictFactory):
    """場所の資源レコード一件分の下書きを、db に触れずに辞書として組む。"""

    location_id = None
    kind = "資源"
    quantity = 1000
    unit = "単位"
    text = ""
    start = None
    end = None


def build_location_resource(**overrides) -> dict:
    """`LocationResourceFactory.build` の薄いラッパー。db には一切触れない。"""
    return LocationResourceFactory.build(**overrides)
