#!/usr/bin/env python3
"""既にいる人物の居場所(`CharacterPlace`)を一件、db へ確定する、claude が呼ぶ入口。

`commit_character` は出自の一件しか書けないので、出自を後から付ける・移った先を足すときに使う。
"""
from __future__ import annotations

from DEM.ai.claude_code.interface.randomizer._base import CommitDraft
from DEM.data_access_logic.query import world_createion_query
from DEM.db.schema import Character, CharacterPlace, Location
from DEM.db.schema_pydantic import to_dict


class CommitCharacterPlace(CommitDraft):
    model = CharacterPlace

    def __init__(self, place: str | dict):
        self.place = place

    def execute(self, session) -> dict:
        data = self.parse(self.place)
        data.pop("id", None)
        self.check_columns(data)
        if data.get("character_id") is None:
            raise ValueError("character_id は必須")
        if data.get("location_id") is None:
            raise ValueError("location_id は必須")

        self.check_exists(session, Character, data["character_id"], "character_id")
        self.check_exists(session, Location, data["location_id"], "location_id")
        place = session.get(Location, data["location_id"])
        world_createion_query.check_within_parent_span(
            place, data.get("start"), data.get("end"), "character_place")

        record = CharacterPlace(**data)
        session.add(record)
        self.finalize(session, record)
        return to_dict(record)
