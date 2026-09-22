#!/usr/bin/env python3
"""同期フラグの下りている話を並べる、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.ai.claude_code.interface.story import _rows
from DEM.ai.claude_code.interface.story._base import StoryQuery


class ListUnsyncedEpisodes(StoryQuery):
    """未同期の話を返す。空なら次の話へ進んでよい。"""

    def __init__(self, story_id: int | None = None):
        self.story_id = story_id

    def execute(self, session) -> list[dict]:
        return _rows.unsynced_episodes(
            session, None if self.story_id is None else int(self.story_id))
