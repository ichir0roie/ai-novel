#!/usr/bin/env python3
"""既にある個体を一件、渡した欄だけ db 上で直す、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Object
from DEM.db.schema_pydantic import to_dict


class UpdateObject(CommitDraft):
    model = Object

    def __init__(self, obj: str | dict):
        self.obj = obj

    def execute(self, session) -> dict:
        data = self.parse(self.obj)
        object_id = data.pop("id", None)
        if object_id is None:
            raise ValueError("id は必須(直す対象の個体)")
        self.check_columns(data)

        record = session.get(Object, object_id)
        if record is None:
            raise ValueError(f"id={object_id} という個体が見つからない")

        for key, value in data.items():
            setattr(record, key, value)
        return to_dict(record)
