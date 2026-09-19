#!/usr/bin/env python3
"""**人物一件を読む**、claude が呼ぶ入口（モード 2-3 の締め）。

一人称・二人称・三人称・口調・性格の値・技・生きている情動・その時点の
居場所・直近の行動が出る。**その話で喋る人物は、書く前にここを通す。**
本文の呼び方はここに従い、書きながら決め直さない
（決め直したくなったら、それはモード 3 の仕事）。

CLI としても呼べる:
    python3 -m DEM.claude_interface.story.read_character <人物id> [時刻]
"""
from __future__ import annotations

import json
import sys

from DEM.claude_interface.story import _rows
from DEM.db.schema import get_session


def read_character(character_id: int, time=None, count: int = 5) -> dict:
    """人物一件を、本文を書くのに要る形でそろえて返す。"""
    with get_session() as session:
        return _rows.character_sheet(session, int(character_id), until=time,
                                     count=int(count))


if __name__ == "__main__":
    character_id = int(sys.argv[1])
    when = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(read_character(character_id, when),
                     ensure_ascii=False, indent=2))
