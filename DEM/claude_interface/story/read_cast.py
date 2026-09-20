#!/usr/bin/env python3
"""**その話に出せる顔ぶれ**を取る、claude が呼ぶ入口(モード 2-3)。

作品の立つ場所の**一つ上**を基準に、その配下にその時点で居る人物と個体を
集め、一人(一群)ずつ直近の出来事・生きている情動・口調を添えて返す。
一つ上を見るのは、その話に出せる者が村の中だけとは限らないからである。

**思いついた名前を先に置かない。** 誰を出せるかはここで決める。
`time` を省くと作品の立つ年。`levels` を上げるともっと広く拾う。
"""
from __future__ import annotations

from DEM.claude_interface.story import _rows
from DEM.claude_interface.story._base import StoryQuery


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
