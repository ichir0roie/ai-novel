#!/usr/bin/env python3
"""ランダムな場所の下書きを一件、辞書として作る、claude が呼ぶ入口。

`DEM.randomizer.random_location_generator.build_location` の薄いラッパー。
**db には一切触れない。** 実在レコードを指す欄（`parent_id`）の存在確認や、
実際の書き込みはしない——それは
`DEM.claude_interface.randomizer.commit_place.CommitPlace` の仕事。

`kind` は既定で `"大陸"`（`overrides` で `kind="村"` のように変えられる）。
**`name` は仮の値のまま返る。** 大陸・国・町・村などの固有名詞は
`IHG/naming.md` の「固有名詞の作り方」に沿って claude が手順で決めてから、
`text`（一言で分かる地理・文化）や `parent_id` と一緒に `CommitPlace` に渡す。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import RandomDraft
from DEM.randomizer.random_location_generator import build_location


class CreateRandomPlace(RandomDraft):
    """ランダムな場所の下書きを一件、辞書として返す。"""

    builder = staticmethod(build_location)
