#!/usr/bin/env python3
"""人物同士の相関の一覧を出す、claude が呼ぶ入口。人物 id を渡すとその人物のものだけに絞る。"""
from __future__ import annotations

from DEM.ai.claude_code.interface.world._base import WorldQuery
from DEM.data_access_logic.query import common_query


class ListCharacterRelations(WorldQuery):
    def __init__(self, character_id: int | None = None):
        self.character_id = character_id

    def select(self):
        return common_query.character_relations_select(self.character_id)

    def row(self, row) -> dict:
        return {"id": row.id, "character_id_1": row.character_id_1,
                "character_id_2": row.character_id_2,
                "relation": row.relation, "text": row.text}
