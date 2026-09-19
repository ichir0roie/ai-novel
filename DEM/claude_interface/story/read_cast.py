#!/usr/bin/env python3
"""**その話に出せる顔ぶれ**を取る、claude が呼ぶ入口（モード 2-3）。

作品の立つ場所の**一つ上**を基準に、その配下にその時点で居る人物と個体を
集め、一人（一群）ずつ直近の出来事・生きている情動・口調を添えて返す。
一つ上を見るのは、その話に出せる者が村の中だけとは限らないからである。

**思いついた名前を先に置かない。** 誰を出せるかはここで決める。
`time` を省くと作品の立つ年。`levels` を上げるともっと広く拾う。

CLI としても呼べる:
    python3 -m DEM.claude_interface.story.read_cast <作品id> [時刻]
"""
from __future__ import annotations

import json
import sys

from DEM.data_access_logic import query
from DEM.db.schema import get_session


def read_cast(story_id: int, time=None, count: int = 5, levels: int = 1) -> dict:
    """その時点の顔ぶれを辞書で返す。"""
    with get_session() as session:
        return query.cast(session, int(story_id), time, count=int(count),
                          levels=int(levels))


if __name__ == "__main__":
    story_id = int(sys.argv[1])
    when = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(read_cast(story_id, when), ensure_ascii=False, indent=2))
