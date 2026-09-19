#!/usr/bin/env python3
"""ランダムな人物の下書きを一件、JSON として作る、claude が呼ぶ入口。

`DEM.randomizer.random_character_generator.build_character` の薄いラッパー。
**db には一切触れない。** 実在レコードを指す欄（`kind_id` `root_place_name`
`born_place_id` `belong_id`）の存在確認や、実際の書き込みはしない——それは
`DEM.claude_interface.randomizer.commit_character` の仕事。

ここが返す JSON を、claude が文脈に合わせて名前・読み・本文・各欄を
書き換えてから `commit_character` に渡す。db にもプロセスにも縛られないので、
このやり取りはターンをまたいでよい。
"""
from __future__ import annotations

import json

from DEM.randomizer.random_character_generator import build_character


def create_random_character(**overrides) -> dict:
    """ランダムな人物の下書きを一件、辞書として返す。

    `overrides` は `build_character` にそのまま渡る（性別・体格・口調・性格
    などその他の欄を先に決めておきたいときに使う）。
    """
    return build_character(**overrides)


def create_random_character_json(**overrides) -> str:
    """`create_random_character` の結果を JSON 文字列で返す（CLI 出力向け）。"""
    return json.dumps(create_random_character(**overrides), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print(create_random_character_json())
