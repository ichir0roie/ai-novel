#!/usr/bin/env python3
"""既にある人物の居場所(`CharacterPlace`)を一件、渡した欄だけ db 上で直す、claude が呼ぶ入口。移った日に前の居場所の `end` を下ろすのに使う。"""
from __future__ import annotations

from DEM.ai.claude_code.interface.randomizer._base import CommitDraft
from DEM.db.schema import Character, CharacterPlace, Location
from DEM.db.schema_pydantic import to_dict


class UpdateCharacterPlace(CommitDraft):
    model = CharacterPlace

    def __init__(self, place: str | dict):
        self.place = place

    def execute(self, session) -> dict:
        data = self.parse(self.place)
        place_id = data.pop("id", None)
        if place_id is None:
            raise ValueError("id は必須(直す対象の居場所)")
        self.check_columns(data)
        self.check_exists(session, Character, data.get("character_id"), "character_id")
        self.check_exists(session, Location, data.get("location_id"), "location_id")

        record = session.get(CharacterPlace, place_id)
        if record is None:
            raise ValueError(f"id={place_id} という居場所が見つからない")

        for key, value in data.items():
            setattr(record, key, value)
        self.finalize(session, record)
        return to_dict(record)
