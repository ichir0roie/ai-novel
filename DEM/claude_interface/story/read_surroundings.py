#!/usr/bin/env python3
"""**人物一人を軸に、その時刻・その居場所の周辺**を読む、claude が呼ぶ入口。

`read_cast` が作品の立つ場所を軸にするのに対して、こちらは**人物**を軸にする。
その人物がその時点で居る場所（とその配下）に、同じ時点で居合わせる人物・
個体（群）、そこで起きた直近の出来事（`reach` 年ぶん）を一度に返す。
ランダム生成・展開の検討材料を広げるのに使う。

`DEM/data_access_logic/query/character_simulation_query.character_around_event`
の薄い呼び出し面。db には触れない。

CLI としても呼べる:
    python3 -m DEM.claude_interface.story.read_surroundings <人物id> <時刻>
"""
from __future__ import annotations

import json
import sys

from DEM.data_access_logic.query import character_simulation_query, common_query
from DEM.db.schema import get_session
from DEM.db.schema_pydantic import to_dict_with


def read_surroundings(character_id: int, time, reach: int = 60) -> dict:
    """その人物の周辺の人物・個体・出来事を辞書で返す。"""
    if time is None:
        raise ValueError("時刻が決まらない（time を渡す）")
    with get_session() as session:
        _, until = common_query.span(time)
        characters, objects, events = character_simulation_query.character_around_event(
            session, int(character_id), until, reach=int(reach))
        return {
            "character_id": int(character_id),
            "time": str(until),
            "reach": int(reach),
            "characters": [to_dict_with(c, text=False) for c in characters],
            "objects": [to_dict_with(o, text=False) for o in objects],
            "events": [to_dict_with(e, relations=common_query.EVENT_RELATIONS)
                       for e in events],
        }


if __name__ == "__main__":
    character_id = int(sys.argv[1])
    when = sys.argv[2]
    print(json.dumps(read_surroundings(character_id, when),
                     ensure_ascii=False, indent=2))
