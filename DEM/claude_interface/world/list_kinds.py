#!/usr/bin/env python3
"""**種別(系統)の一覧**を出す、claude が呼ぶ入口。

人物や個体の `kind_id` に渡す id をここで拾う。db には書き込まない。
"""
from __future__ import annotations

from DEM.claude_interface.world._base import WorldQuery
from DEM.data_access_logic.query import common_query


class ListKinds(WorldQuery):
    """種別を一覧で返す。"""

    def select(self):
        return common_query.kinds_select()

    def row(self, row) -> dict:
        return {"id": row.id, "name": row.name, "read": row.read}
