#!/usr/bin/env python3
"""既にある人物の筋書きを一件、渡した欄だけ db 上で直す、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import CharacterPlot
from DEM.db.schema_pydantic import to_dict


class UpdateCharacterPlot(CommitDraft):
    model = CharacterPlot

    def __init__(self, plot: str | dict):
        self.plot = plot

    def execute(self, session) -> dict:
        data = self.parse(self.plot)
        plot_id = data.pop("id", None)
        if plot_id is None:
            raise ValueError("id は必須(直す対象の筋書き)")
        self.check_columns(data)

        record = session.get(CharacterPlot, plot_id)
        if record is None:
            raise ValueError(f"id={plot_id} という人物の筋書きが見つからない")

        for key, value in data.items():
            setattr(record, key, value)
        return to_dict(record)
