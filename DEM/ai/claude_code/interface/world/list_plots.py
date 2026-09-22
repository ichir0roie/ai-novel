#!/usr/bin/env python3
"""筋書きの一覧を出す、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.ai.claude_code.interface.world._base import WorldQuery
from DEM.data_access_logic.query import common_query


class ListPlots(WorldQuery):
    def select(self):
        return common_query.plots_select()

    def row(self, row) -> dict:
        return {"id": row.id, "location_id": row.location_id, "text": row.text,
                "start": row.start, "end": row.end}
