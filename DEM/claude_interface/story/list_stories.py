#!/usr/bin/env python3
"""**作品の一覧**を出す、claude が呼ぶ入口。

どの作品があるか、どの世界線のどこに立つか、何話まで書いたか、
未同期の話が残っていないか(`unsynced`)が一枚で分かる。
作品の id をここで拾って、以降の入口に渡す。
"""
from __future__ import annotations

from DEM.claude_interface.story import _rows
from DEM.claude_interface.story._base import StoryQuery


class ListStories(StoryQuery):
    """作品を全件、見出しの辞書で返す。"""

    def execute(self, session) -> list[dict]:
        return _rows.stories(session)
