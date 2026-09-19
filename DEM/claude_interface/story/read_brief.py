#!/usr/bin/env python3
"""**世界の断面**を取る、claude が呼ぶ入口（モード 2-3）。

設定を頭から読み直さないための一枚。その場所の道筋、配下でまだ張っている
出来事、`reach` 年ぶんの直近の出来事、そこで使う語、いま居る者が出る。

**`full=True` を付けない。** 付けると住人が知らない裏（種別 `裏` `伏線`）
まで出て、それを本文に書いてしまう。裏を設計するときだけ付ける。

CLI としても呼べる:
    python3 -m DEM.claude_interface.story.read_brief <場所id> <時刻>
"""
from __future__ import annotations

import json
import sys

from DEM.claude_interface.story import _rows
from DEM.db.schema import get_session


def read_brief(place_id: int, time, reach: int = 60, full: bool = False) -> dict:
    """その場所・その時点の断面を辞書で返す。"""
    with get_session() as session:
        return _rows.brief(session, int(place_id), time, reach=int(reach),
                           full=full)


if __name__ == "__main__":
    print(json.dumps(read_brief(int(sys.argv[1]), sys.argv[2]),
                     ensure_ascii=False, indent=2))
