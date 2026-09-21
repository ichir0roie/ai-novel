#!/usr/bin/env python3
"""筋書き(`Plot`)を一件、db へ確定する、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Location, Plot
from DEM.db.schema_pydantic import to_dict


class CommitPlot(CommitDraft):
    model = Plot

    def __init__(self, plot: str | dict):
        self.plot = plot

    def execute(self, session) -> dict:
        data = self.parse(self.plot)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("text"):
            raise ValueError("text は必須")

        self.check_exists(session, Location, data.get("location_id"), "location_id")

        record = Plot(**data)
        session.add(record)
        session.commit()
        return to_dict(record)
