#!/usr/bin/env python3
"""ランダムな出来事の下書きを一件、JSON として作る、claude が呼ぶ入口。

`DEM.randomizer.random_event_generator.build_event` の薄いラッパー。
**db には一切触れない。** 実在レコードを指す欄（`place_id` `character_id`
`object_id` `parent_event_id`）の存在確認や、実際の書き込みはしない——それは
`DEM.claude_interface.randomizer.commit_event` の仕事。

ここが返す JSON を、claude が文脈に合わせて `name` `kind` `time` `text` や
各欄を書き換えてから `commit_event` に渡す。
"""
from __future__ import annotations

import json

from DEM.randomizer.random_event_generator import build_event


def create_random_event(**overrides) -> dict:
    """ランダムな出来事の下書きを一件、辞書として返す。"""
    return build_event(**overrides)


def create_random_event_json(**overrides) -> str:
    """`create_random_event` の結果を JSON 文字列で返す（CLI 出力向け）。"""
    return json.dumps(create_random_event(**overrides), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print(create_random_event_json())
