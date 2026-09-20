#!/usr/bin/env python3
"""ランダムな出来事の下書きを一件、辞書として作る、claude が呼ぶ入口。

`DEM.randomizer.random_event_generator.build_event` の薄いラッパー。
**db には一切触れない。** 実在レコードを指す欄(`location_id` `character_ids`
`object_ids` `parent_event_id`)の存在確認や、実際の書き込みはしない——それは
`DEM.claude_interface.randomizer.commit_event.CommitEvent` の仕事。

ここが返す辞書を、claude が文脈に合わせて `name` `kind` `time` `text` や
各欄を書き換えてから `CommitEvent` に渡す。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import RandomDraft
from DEM.randomizer.random_event_generator import build_event


class CreateRandomEvent(RandomDraft):
    """ランダムな出来事の下書きを一件、辞書として返す。"""

    builder = staticmethod(build_event)
