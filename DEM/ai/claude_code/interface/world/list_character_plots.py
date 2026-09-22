#!/usr/bin/env python3
"""人物の筋書きの一覧を出す、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.ai.claude_code.interface.world._base import WorldQuery
from DEM.data_access_logic.query import common_query


class ListCharacterPlots(WorldQuery):
    def select(self):
        return common_query.character_plots_select()

    def row(self, row) -> dict:
        return {"id": row.id, "character_id": row.character_id, "text": row.text,
                "start": row.start, "end": row.end}
