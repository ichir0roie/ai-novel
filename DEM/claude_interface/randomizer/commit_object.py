#!/usr/bin/env python3
"""個体(群)を一件、db へ確定する、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.data_access_logic.query import world_createion_query
from DEM.db.schema import Location, Object
from DEM.db.schema_pydantic import to_dict


class CommitObject(CommitDraft):
    model = Object

    def __init__(self, obj: str | dict):
        self.obj = obj

    def execute(self, session) -> dict:
        data = self.parse(self.obj)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("name"):
            raise ValueError("name は必須")
        if "仮の群" in str(data.get("name")):
            raise ValueError(
                f"name={data['name']!r} は下書きの仮の値。"
                "IHG/naming.md に沿って名を決めてから確定する")

        self.check_exists(session, Location, data.get("root_place_name"), "root_place_name")
        self._check_capacity(session, data)
        self._check_span(session, data)
        self._check_plot(session, data)

        record = Object(**data)
        session.add(record)
        session.commit()
        return to_dict(record)

    @staticmethod
    def _check_capacity(session, data: dict) -> None:
        place_id = data.get("root_place_name")
        if place_id is None:
            return
        count = session.scalar(
            world_createion_query.object_count_at_place_select(place_id))
        if count >= world_createion_query.MAX_PER_LOCATION:
            raise ValueError(
                f"root_place_name={place_id} には既に個体が "
                f"{world_createion_query.MAX_PER_LOCATION} 件あり、これ以上作れない")

    @staticmethod
    def _check_span(session, data: dict) -> None:
        place_id = data.get("root_place_name")
        if place_id is None:
            return
        place = session.get(Location, place_id)
        world_createion_query.check_within_parent_span(
            place, data.get("start"), data.get("end"), "object")

    @staticmethod
    def _check_plot(session, data: dict) -> None:
        place_id = data.get("root_place_name")
        if place_id is None:
            return
        world_createion_query.check_has_plot(session, place_id, "object")
