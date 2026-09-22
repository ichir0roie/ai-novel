#!/usr/bin/env python3
"""作品の一覧を出す、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.ai.claude_code.claude_interface.story import _rows
from DEM.ai.claude_code.claude_interface.story._base import StoryQuery


class ListStories(StoryQuery):
    """作品を全件、見出しの辞書で返す。"""

    def execute(self, session) -> list[dict]:
        return _rows.stories(session)
