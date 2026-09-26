#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code.interface.world._base import WorldQuery
from data_access_logic.query import common_query


class ListCharacters(WorldQuery):
    def select(self):
        return common_query.characters_select()

    def row(self, row) -> dict:
        place = row.places[0] if row.places else None
        parameters = row.parameters_at()
        return {
            "id": row.id, "name": row.name, "family_name": parameters["family_name"],
            "kind": row.kind, "text": row.text,
            "sex": parameters["sex"], "tone": parameters["tone"], "dialect": parameters["dialect"],
            "place_id": place.location_id if place else None,
        }
