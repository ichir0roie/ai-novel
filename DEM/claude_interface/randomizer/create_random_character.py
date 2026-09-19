#!/usr/bin/env python3
"""ランダムな人物の下書きを一件、辞書として作る、claude が呼ぶ入口。

`DEM.randomizer.random_character_generator.build_character` の薄いラッパー。
**db には一切触れない。** 実在レコードを指す欄（`kind_id` `root_place_name`
`born_place_id` `belong_id`）の存在確認や、実際の書き込みはしない——それは
`DEM.claude_interface.randomizer.commit_character.CommitCharacter` の仕事。

ここが返す辞書を、claude が文脈に合わせて名前・読み・本文・各欄を
書き換えてから `CommitCharacter` に渡す。db にもプロセスにも縛られないので、
このやり取りはターンをまたいでよい。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import RandomDraft
from DEM.randomizer.random_character_generator import build_character


class CreateRandomCharacter(RandomDraft):
    """ランダムな人物の下書きを一件、辞書として返す。

    `overrides` は `build_character` にそのまま渡る（性別・体格・口調・性格
    などその他の欄を先に決めておきたいときに使う）。
    """

    builder = staticmethod(build_character)
