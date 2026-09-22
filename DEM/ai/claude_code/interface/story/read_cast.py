#!/usr/bin/env python3
"""その話に出せる顔ぶれを取る、claude が呼ぶ入口。

作品の立つ場所から `levels` 段のぼった場所を基準に、配下に居る人物を集める。
`time` を省くと作品の立つ年。
"""
from __future__ import annotations

from DEM.ai.claude_code.interface.story import _rows
from DEM.ai.claude_code.interface.story._base import StoryQuery


class ReadCast(StoryQuery):
    """その時点の顔ぶれを辞書で返す。"""

    def __init__(self, story_id: int, time=None, count: int = 5, levels: int = 1):
        self.story_id = story_id
        self.time = time
        self.count = count
        self.levels = levels

    def execute(self, session) -> dict:
        return _rows.cast(session, int(self.story_id), self.time,
                          count=int(self.count), levels=int(self.levels))
