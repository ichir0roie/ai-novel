#!/usr/bin/env python3
"""人物を一件、db へ確定する、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.ai.claude_code.claude_interface.randomizer._base import CommitDraft
from DEM.data_access_logic.query import world_createion_query
from DEM.db.schema import Character, CharacterPlace, Location
from DEM.db.schema_pydantic import to_dict


class CommitCharacter(CommitDraft):
    """`place_id` は列ではなく、出自を表す `CharacterPlace` の一件として書き込む。"""

    model = Character

    def __init__(self, character: str | dict):
        self.character = character

    def execute(self, session) -> dict:
        data = self.parse(self.character)
        data.pop("id", None)
        place_id = data.pop("place_id", None)
        self.check_columns(data)

        self.check_exists(session, Location, place_id, "place_id")
        self._check_capacity(session, place_id, data.get("start"))
        self._check_span(session, place_id, data)
        self._check_plot(session, place_id)

        record = Character(**data)
        session.add(record)
        session.flush()  # CharacterPlace の character_id に使う id を先に確定させる
        if place_id is not None:
            session.add(CharacterPlace(
                character_id=record.id, location_id=place_id,
                start=data.get("start"), end=data.get("end")))
        self.finalize(session, record)
        return to_dict(record)

    @staticmethod
    def _check_capacity(session, place_id: int | None, stamp) -> None:
        if place_id is None or stamp is None:
            return
        count = session.scalar(
            world_createion_query.character_count_at_place_select(place_id, stamp))
        if count >= world_createion_query.MAX_CHARACTERS_PER_LOCATION:
            raise ValueError(
                f"place_id={place_id} には既に人物が "
                f"{world_createion_query.MAX_CHARACTERS_PER_LOCATION} 件あり、これ以上作れない")

    @staticmethod
    def _check_span(session, place_id: int | None, data: dict) -> None:
        if place_id is None:
            return
        place = session.get(Location, place_id)
        world_createion_query.check_within_parent_span(
            place, data.get("start"), data.get("end"), "character")

    @staticmethod
    def _check_plot(session, place_id: int | None) -> None:
        if place_id is None:
            return
        world_createion_query.check_has_plot(session, place_id, "character")
