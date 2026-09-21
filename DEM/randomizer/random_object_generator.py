#!/usr/bin/env python3
"""factory_boy でランダムな個体(Object)一件分の下書きを**辞書**として組む。

db には一切触れない。`DEM.db.schema.Object` にも依存しない(列名を合わせて
いるだけで、import はしていない)。

**固有名詞(`name`)は仮の値のまま返す。** 国・組織・商会などの名は
`IHG/naming.md`(「対象ごとの当て方」の組織・機関)に沿って手順で決めるもので、
乱数で機械的に埋めるものではない。実在レコードを指す欄(`root_place_name`)も、
存在確認や書き込みと同じく呼び出し側
(`DEM.claude_interface.randomizer.commit_object`)の仕事なのでここでは埋めない。

**個体に `kind` の欄は無い**(種別の表は廃止した)。国なのか組織なのか商会
なのかは `text`(個体の説明)の中に書く。
"""
from __future__ import annotations

import factory

# 世界線への影響度(`world_influence`)の既定の幅。
# 大きいほどその個体の一手が世界に及ぶ(`DEM/db/schema.py` の ObjectBase)。
_INFLUENCE_RANGE = (0, 3)


class ObjectFactory(factory.DictFactory):
    """個体レコード一件分の下書きを、db に触れずに辞書として組む。"""

    name = factory.Sequence(lambda n: f"仮の群{n}")
    read = ""
    text = ""

    world_influence = factory.Faker(
        "random_int", min=_INFLUENCE_RANGE[0], max=_INFLUENCE_RANGE[1])

    # 実在レコードを指す欄・時刻。呼び出し側が上書きする前提で None のまま。
    root_place_name = None
    start = None
    end = None


def build_object(**overrides) -> dict:
    """`ObjectFactory.build` の薄いラッパー。db には一切触れない。"""
    return ObjectFactory.build(**overrides)
