#!/usr/bin/env python3
"""factory_boy でランダムな場所(Location)一件分の下書きを**辞書**として組む。

db には一切触れない。`DEM.db.schema.Location` にも依存しない(列名を合わせて
いるだけで、import はしていない)。

**固有名詞(`name`)は仮の値のまま返す。** 大陸・国・町・村などの固有名詞は
`IHG/naming.md` の「固有名詞の作り方」に沿って手順で決めるものであって、
乱数で機械的に埋めるものではない(意味を決める→言語を一つ引く→その言語で
言う→カタカナにする、という手順そのものに判断が要る)。実在レコードを指す欄
(`parent_id`)も、存在確認や書き込みと同じく呼び出し側
(`DEM.claude_interface.randomizer.commit_place`)の仕事なのでここでは埋めない。
"""
from __future__ import annotations

import factory


class LocationFactory(factory.DictFactory):
    """場所レコード一件分の下書きを、db に触れずに辞書として組む。"""

    name = factory.Sequence(lambda n: f"仮の土地{n}")
    kind = "大陸"
    text = ""

    parent_id = None
    location_world = None
    location_planet = None
    location_longitude = None
    location_latitude = None
    location_altitude = None
    area = None
    environment = None
    start = None
    end = None


def build_location(**overrides) -> dict:
    """`LocationFactory.build` の薄いラッパー。db には一切触れない。"""
    return LocationFactory.build(**overrides)
