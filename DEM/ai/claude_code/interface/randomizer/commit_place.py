#!/usr/bin/env python3
"""場所を一件、db へ確定する、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.ai.claude_code.claude_interface.randomizer._base import CommitDraft
from DEM.data_access_logic.query import world_createion_query
from DEM.db.schema import Location
from DEM.db.schema_pydantic import to_dict


class CommitPlace(CommitDraft):
    model = Location

    def __init__(self, place: str | dict):
        self.place = place

    def execute(self, session) -> dict:
        data = self.parse(self.place)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("name"):
            raise ValueError("name は必須")
        if not data.get("kind"):
            raise ValueError("kind は必須")

        self.check_exists(session, Location, data.get("parent_id"), "parent_id")
        self._check_area(session, data)
        self._check_span(session, data)

        record = Location(**data)
        session.add(record)
        self.finalize(session, record)
        return to_dict(record)

    @staticmethod
    def _check_area(session, data: dict) -> None:
        area = data.get("area")
        parent_id = data.get("parent_id")
        if area is None or parent_id is None:
            return

        parent = session.get(Location, parent_id)
        if parent.area is None:
            return

        if not area < parent.area:
            raise ValueError(
                f"area={area} が親(id={parent_id})の広さ {parent.area} 未満でない")

        siblings_area = session.scalar(
            world_createion_query.siblings_area_sum_select(parent_id))
        if siblings_area + area > parent.area:
            raise ValueError(
                f"area={area} を足すと、親(id={parent_id})の広さ {parent.area} を"
                f"兄弟の合計 {siblings_area} が超える")

    @staticmethod
    def _check_span(session, data: dict) -> None:
        parent_id = data.get("parent_id")
        if parent_id is None:
            return
        parent = session.get(Location, parent_id)
        world_createion_query.check_within_parent_span(
            parent, data.get("start"), data.get("end"), "location")
