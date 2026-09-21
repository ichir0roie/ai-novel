#!/usr/bin/env python3
"""既にある場所を一件、渡した欄だけ db 上で直す、claude が呼ぶ入口。"""
from __future__ import annotations

from sqlalchemy import func, select

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Location
from DEM.db.schema_pydantic import to_dict


class UpdatePlace(CommitDraft):
    model = Location

    def __init__(self, place: str | dict):
        self.place = place

    def execute(self, session) -> dict:
        data = self.parse(self.place)
        place_id = data.pop("id", None)
        if place_id is None:
            raise ValueError("id は必須(直す対象の場所)")
        self.check_columns(data)

        record = session.get(Location, place_id)
        if record is None:
            raise ValueError(f"id={place_id} という場所が見つからない")

        if "area" in data:
            self._check_area(session, record, data["area"])

        for key, value in data.items():
            setattr(record, key, value)
        session.commit()
        return to_dict(record)

    @staticmethod
    def _check_area(session, record: Location, area) -> None:
        if area is None or record.parent_id is None:
            return
        parent = session.get(Location, record.parent_id)
        if parent is None or parent.area is None:
            return
        if not area < parent.area:
            raise ValueError(
                f"area={area} が親(id={record.parent_id})の広さ {parent.area} 未満でない")

        siblings_area = session.scalar(
            select(func.coalesce(func.sum(Location.area), 0))
            .where(Location.parent_id == record.parent_id, Location.id != record.id))
        if siblings_area + area > parent.area:
            raise ValueError(
                f"area={area} を足すと、親(id={record.parent_id})の広さ "
                f"{parent.area} を兄弟(自分を除く)の合計 {siblings_area} が超える")
