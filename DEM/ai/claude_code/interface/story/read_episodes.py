#!/usr/bin/env python3
"""直前の N 話を読む、claude が呼ぶ入口。

    ReadEpisodes(1).run()                       最新 10 話の本文
    ReadEpisodes(1, before=15).run()             15 話の前 10 話
    ReadEpisodes(1, count=50, text=False).run()  話数と題だけの一覧
"""
from __future__ import annotations

from DEM.ai.claude_code.claude_interface.story import _rows
from DEM.ai.claude_code.claude_interface.story._base import StoryQuery


class ReadEpisodes(StoryQuery):
    """その作品の話を古い順に返す。`text=False` なら話数と題だけ。"""

    def __init__(self, story_id: int, count: int = 10, before: int | None = None,
                 text: bool = True):
        self.story_id = story_id
        self.count = count
        self.before = before
        self.text = text

    def execute(self, session) -> list[dict]:
        return _rows.episodes(session, int(self.story_id), count=int(self.count),
                              before=self.before, text=self.text)
