#!/usr/bin/env python3
"""世界の断面(場所の道筋・張っている出来事・直近の出来事・語・いま居る者)を取る、claude が呼ぶ入口。

`full=True` で種別 `裏` `伏線` の出来事も含める(既定は除く)。
"""
from __future__ import annotations

from DEM.ai.claude_code.interface.story import _rows
from DEM.ai.claude_code.interface.story._base import StoryQuery


class ReadBrief(StoryQuery):
    """その場所・その時点の断面を辞書で返す。"""

    def __init__(self, place_id: int, time, reach: int = 60, full: bool = False):
        self.place_id = place_id
        self.time = time
        self.reach = reach
        self.full = full

    def execute(self, session) -> dict:
        return _rows.brief(session, int(self.place_id), self.time,
                           reach=int(self.reach), full=self.full)
