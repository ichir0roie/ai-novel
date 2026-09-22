#!/usr/bin/env python3
"""人物一人を軸に、その時刻・その居場所の周辺(居合わせる人物、直近の出来事)を読む、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.ai.claude_code.interface.story import _rows
from DEM.ai.claude_code.interface.story._base import StoryQuery
from DEM.data_access_logic.query import character_simulation_query, common_query
from DEM.db.schema_pydantic import to_dict_with


class ReadSurroundings(StoryQuery):
    """その人物の周辺の人物・出来事を辞書で返す。"""

    def __init__(self, character_id: int, time, reach: int = 60):
        if time is None:
            raise ValueError("時刻が決まらない(time を渡す)")
        self.character_id = character_id
        self.time = time
        self.reach = reach

    def execute(self, session) -> dict:
        _, until = common_query.span(self.time)
        characters, events = character_simulation_query.character_around_event(
            session, int(self.character_id), until, reach=int(self.reach))
        return {
            "character_id": int(self.character_id),
            "time": str(until),
            "reach": int(self.reach),
            "characters": [to_dict_with(c, text=False) for c in characters],
            "events": [_rows.event_row(e) for e in events],
        }
