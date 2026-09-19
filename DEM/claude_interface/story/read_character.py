#!/usr/bin/env python3
"""**人物一件を読む**、claude が呼ぶ入口（モード 2-3 の締め）。

一人称・二人称・三人称・口調・性格の値・技・生きている情動・その時点の
居場所・直近の行動が出る。**その話で喋る人物は、書く前にここを通す。**
本文の呼び方はここに従い、書きながら決め直さない
（決め直したくなったら、それはモード 3 の仕事）。
"""
from __future__ import annotations

from DEM.claude_interface.story import _rows
from DEM.claude_interface.story._base import StoryQuery


class ReadCharacter(StoryQuery):
    """人物一件を、本文を書くのに要る形でそろえて返す。"""

    def __init__(self, character_id: int, time=None, count: int = 5):
        self.character_id = character_id
        self.time = time
        self.count = count

    def execute(self, session) -> dict:
        return _rows.character_sheet(session, int(self.character_id),
                                     until=self.time, count=int(self.count))
