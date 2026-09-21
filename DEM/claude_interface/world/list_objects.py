#!/usr/bin/env python3
"""個体(群)の一覧を出す、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.claude_interface.world._base import WorldQuery
from DEM.data_access_logic.query import common_query


class ListObjects(WorldQuery):
    def select(self):
        return common_query.objects_select()

    def row(self, row) -> dict:
        return {"id": row.id, "name": row.name}
