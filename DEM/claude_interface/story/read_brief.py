#!/usr/bin/env python3
"""**世界の断面**を取る、claude が呼ぶ入口(モード 2-3)。

設定を頭から読み直さないための一枚。その場所の道筋、配下でまだ張っている
出来事、`reach` 年ぶんの直近の出来事、そこで使う語、いま居る者が出る。

**`full=True` を付けない。** 付けると住人が知らない裏(種別 `裏` `伏線`)
まで出て、それを本文に書いてしまう。裏を設計するときだけ付ける。
"""
from __future__ import annotations

from DEM.claude_interface.story import _rows
from DEM.claude_interface.story._base import StoryQuery


class ReadBrief(StoryQuery):
    """その場所・その時点の断面を辞書で返す。"""

    def __init__(self, place_id: int, time, reach: int = 60, full: bool = False):
        self.place_id = place_id
        self.time = time
        self.reach = reach
        self.full = full

    def execute(self, session) -> dict:
        return _rows.brief(session, int(self.place_id), self.time,
                           reach=int(self.reach), full=self.full)
