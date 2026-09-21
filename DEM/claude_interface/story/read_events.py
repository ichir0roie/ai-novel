#!/usr/bin/env python3
"""出来事を引く、claude が呼ぶ入口。

    ReadEvents(time="4354").run()       その年の出来事と行動を全部
    ReadEvents(record_id=8).run()       その id に掛かるもの(場所なら
                                        そこで起きたこと、人物なら行動、
                                        出来事ならぶら下がる行動)
"""
from __future__ import annotations

from DEM.claude_interface.story import _rows
from DEM.claude_interface.story._base import StoryQuery


class ReadEvents(StoryQuery):
    """時刻か id で出来事を引く。どちらか一方を渡す。"""

    def __init__(self, time=None, record_id: int | None = None,
                 limit: int | None = None, until=None):
        if (time is None) == (record_id is None):
            raise ValueError("time か record_id のどちらか一方だけを渡す")
        self.time = time
        self.record_id = record_id
        self.limit = limit
        self.until = until

    def execute(self, session) -> list[dict]:
        if self.time is not None:
            return _rows.events_at(session, self.time, limit=self.limit)
        return _rows.events_of(session, int(self.record_id), until=self.until,
                               limit=self.limit)
