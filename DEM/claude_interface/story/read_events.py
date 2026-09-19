#!/usr/bin/env python3
"""**出来事を引く**、claude が呼ぶ入口。

引く条件は時刻とレコードの id だけ。SQL は組み立てない。

    read_events(time="4354")        その年の出来事と行動を全部
    read_events(record_id=8)        その id に掛かるもの（場所なら
                                    そこで起きたこと、人物なら行動、
                                    出来事ならぶら下がる行動）

CLI としても呼べる:
    python3 -m DEM.claude_interface.story.read_events <時刻|id>
"""
from __future__ import annotations

import json
import sys

from DEM.claude_interface.story import _rows
from DEM.db.schema import get_session


def read_events(time=None, record_id: int | None = None, limit: int | None = None,
                until=None) -> list[dict]:
    """時刻か id で出来事を引く。どちらか一方を渡す。"""
    if (time is None) == (record_id is None):
        raise ValueError("time か record_id のどちらか一方だけを渡す")
    with get_session() as session:
        if time is not None:
            return _rows.events_at(session, time, limit=limit)
        return _rows.events_of(session, int(record_id), until=until, limit=limit)


if __name__ == "__main__":
    argument = sys.argv[1]
    result = (read_events(record_id=int(argument)) if argument.isdigit()
              and len(argument) < 5 else read_events(time=argument))
    print(json.dumps(result, ensure_ascii=False, indent=2))
