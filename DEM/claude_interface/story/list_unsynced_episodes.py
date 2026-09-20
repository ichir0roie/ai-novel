#!/usr/bin/env python3
"""**同期フラグの下りている話を並べる**、claude が呼ぶ入口(モード 2-0)。

その話で起きたことが台帳へ戻っていない話が残っているあいだ、次の話の
材料(断面・顔ぶれ)は一話ぶん古い。**一件でも出たら、モード 2 をいったん
置いてモード 3 をやる。**
"""
from __future__ import annotations

from DEM.claude_interface.story import _rows
from DEM.claude_interface.story._base import StoryQuery


class ListUnsyncedEpisodes(StoryQuery):
    """未同期の話を返す。空なら次の話へ進んでよい。"""

    def __init__(self, story_id: int | None = None):
        self.story_id = story_id

    def execute(self, session) -> list[dict]:
        return _rows.unsynced_episodes(
            session, None if self.story_id is None else int(self.story_id))
