#!/usr/bin/env python3
"""人物の一覧を出す、claude が呼ぶ入口。"""
from __future__ import annotations

from ai.claude_code.interface.world._base import WorldQuery
from data_access_logic.query import common_query


class ListCharacters(WorldQuery):
    def select(self):
        return common_query.characters_select()

    def row(self, row) -> dict:
        place = row.places[0] if row.places else None
        return {
            "id": row.id, "name": row.name, "kind": row.kind, "text": row.text,
            "sex": row.sex, "tone": row.tone,
            "place_id": place.location_id if place else None,
        }
