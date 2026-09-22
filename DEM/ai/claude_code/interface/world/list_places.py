#!/usr/bin/env python3
"""場所の一覧を出す、claude が呼ぶ入口。`kind` を渡すとその種別だけに絞る。"""
from __future__ import annotations

from DEM.ai.claude_code.interface.world._base import WorldQuery
from DEM.data_access_logic.query import common_query


class ListPlaces(WorldQuery):
    def __init__(self, kind: str | None = None):
        self.kind = kind

    def select(self):
        return common_query.places_select(kind=self.kind)

    def row(self, row) -> dict:
        return {"id": row.id, "name": row.name, "kind": row.kind,
                "parent_id": row.parent_id,
                "sample_region": row.sample_region, "sample_culture": row.sample_culture,
                "sample_era": row.sample_era}
