#!/usr/bin/env python3
"""ランダムな人物の下書きを一件、辞書として作る、claude が呼ぶ入口。

`DEM.randomizer.random_character_generator.build_character` の薄いラッパー。
**db には一切触れない。** 実在レコードを指す欄(`root_place_name`
`born_place_id` `belong_id`)の存在確認や、実際の書き込みはしない——それは
`DEM.claude_interface.randomizer.commit_character.CommitCharacter` の仕事。

ここが返す辞書を、claude が文脈に合わせて名前・読み・本文・各欄を
書き換えてから `CommitCharacter` に渡す。db にもプロセスにも縛られないので、
このやり取りはターンをまたいでよい。

**呼ぶ前に `DEM.claude_interface.world.list_plots.ListPlots().run()` で
今の筋書きを読む。** その人物が立つ場所に掛かる筋書き・場所を問わない
筋書きを踏まえて、`text`(本文)・性格の各軸・持たせたい技の方向づけを
決めてから、この下書きの各欄を書き換える(ここ自体は乱数任せの下書きで、
筋書きを読むのは呼び出し側の仕事)。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import RandomDraft
from DEM.randomizer.random_character_generator import build_character


class CreateRandomCharacter(RandomDraft):
    """ランダムな人物の下書きを一件、辞書として返す。

    `overrides` は `build_character` にそのまま渡る(性別・体格・口調・性格
    などその他の欄を先に決めておきたいときに使う)。
    """

    builder = staticmethod(build_character)
