#!/usr/bin/env python3
"""**個体(群)の一覧**を出す、claude が呼ぶ入口。

人物の `belong_id`(所属)に渡す id をここで拾う。`kind` を渡すと
その種別の名前(例: `"集落"`)だけに絞る。db には書き込まない。
"""
from __future__ import annotations

from DEM.claude_interface.world._base import WorldQuery
from DEM.data_access_logic.query import common_query
from DEM.db.schema_pydantic import relation_names


class ListObjects(WorldQuery):
    """個体(群)を一覧で返す。"""

    def __init__(self, kind: str | None = None):
        self.kind = kind

    def select(self):
        return common_query.objects_select(kind=self.kind)

    def row(self, row) -> dict:
        return {"id": row.id, "name": row.name, "kind_id": row.kind_id,
                **relation_names(row, ["kind"])}
