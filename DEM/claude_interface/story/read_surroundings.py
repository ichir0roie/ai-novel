#!/usr/bin/env python3
"""**人物一人を軸に、その時刻・その居場所の周辺**を読む、claude が呼ぶ入口。

`read_cast` が作品の立つ場所を軸にするのに対して、こちらは**人物**を軸にする。
その人物がその時点で居る場所（とその配下）に、同じ時点で居合わせる人物・
個体（群）、そこで起きた直近の出来事（`reach` 年ぶん）を一度に返す。
ランダム生成・展開の検討材料を広げるのに使う。

`DEM/data_access_logic/query/character_simulation_query.character_around_event`
の薄い呼び出し面。db には触れない。
"""
from __future__ import annotations

from DEM.claude_interface.story import _rows
from DEM.claude_interface.story._base import StoryQuery
from DEM.data_access_logic.query import character_simulation_query, common_query
from DEM.db.schema_pydantic import to_dict_with


class ReadSurroundings(StoryQuery):
    """その人物の周辺の人物・個体・出来事を辞書で返す。"""

    def __init__(self, character_id: int, time, reach: int = 60):
        if time is None:
            raise ValueError("時刻が決まらない（time を渡す）")
        self.character_id = character_id
        self.time = time
        self.reach = reach

    def execute(self, session) -> dict:
        _, until = common_query.span(self.time)
        characters, objects, events = character_simulation_query.character_around_event(
            session, int(self.character_id), until, reach=int(self.reach))
        return {
            "character_id": int(self.character_id),
            "time": str(until),
            "reach": int(self.reach),
            "characters": [to_dict_with(c, text=False) for c in characters],
            "objects": [to_dict_with(o, text=False) for o in objects],
            "events": [_rows.event_row(e) for e in events],
        }
