#!/usr/bin/env python3
"""場所の筋書き(`Plot`)を一件、db から削除する、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.ai.claude_code.interface._base import UnknownRecordError
from DEM.ai.claude_code.interface.randomizer._base import CommitDraft
from DEM.db.schema import Plot


class DeletePlot(CommitDraft):
    """筋書きを一件削除して、消す直前の中身を辞書で返す。"""

    model = Plot

    def __init__(self, plot_id: int):
        self.plot_id = plot_id

    def execute(self, session) -> dict:
        record = session.get(Plot, int(self.plot_id))
        if record is None:
            raise UnknownRecordError(
                f"plot_id={self.plot_id} という id の plot が見つからない")

        data = {"id": record.id, "location_id": record.location_id, "text": record.text}
        session.delete(record)
        return data
