#!/usr/bin/env python3
"""人物の一覧を出す、claude が呼ぶ入口。情動を持つかどうかも返す。"""
from __future__ import annotations

from DEM.claude_interface.world._base import WorldQuery
from DEM.data_access_logic.query import common_query


class ListCharacters(WorldQuery):
    def select(self):
        return common_query.characters_select()

    def row(self, row) -> dict:
        return {
            "id": row.id, "name": row.name, "text": row.text,
            "sex": row.sex, "tone": row.tone,
            "born_place_id": row.born_place_id, "belong_id": row.belong_id,
            "emotion_count": len(row.emotions),
        }
