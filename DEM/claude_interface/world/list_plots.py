#!/usr/bin/env python3
"""**筋書きの一覧**を出す、claude が呼ぶ入口。

`location_id` が空の行は、場所を問わず全ての出来事生成に渡る筋書き。
`start`〜`end` が空の行は、期間を問わず渡り続ける。
新しい筋書きを足す前に、重複や矛盾が無いかをここで確かめる。
"""
from __future__ import annotations

from DEM.claude_interface.world._base import WorldQuery
from DEM.data_access_logic.query import common_query


class ListPlots(WorldQuery):
    """筋書きを一覧で返す。db には書き込まない。"""

    def select(self):
        return common_query.plots_select()

    def row(self, row) -> dict:
        return {"id": row.id, "location_id": row.location_id, "text": row.text,
                "start": row.start, "end": row.end}
