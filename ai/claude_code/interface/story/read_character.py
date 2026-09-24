#!/usr/bin/env python3
"""人物一件を読む、claude が呼ぶ入口。口調・性格・生きている情動・居場所・直近の行動が出る。"""
from __future__ import annotations

from ai.claude_code.interface.story import _rows
from ai.claude_code.interface.story._base import StoryQuery


class ReadCharacter(StoryQuery):
    """人物一件を、本文を書くのに要る形でそろえて返す。"""

    def __init__(self, character_id: int, time=None, count: int = 5):
        self.character_id = character_id
        self.time = time
        self.count = count

    def execute(self, session) -> dict:
        return _rows.character_sheet(session, int(self.character_id),
                                     until=self.time, count=int(self.count))
