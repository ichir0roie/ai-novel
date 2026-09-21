#!/usr/bin/env python3
"""既にある人物を一件、渡した欄だけ db 上で直す、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Character
from DEM.db.schema_pydantic import to_dict


class UpdateCharacter(CommitDraft):
    model = Character

    def __init__(self, character: str | dict):
        self.character = character

    def execute(self, session) -> dict:
        data = self.parse(self.character)
        character_id = data.pop("id", None)
        if character_id is None:
            raise ValueError("id は必須(直す対象の人物)")
        self.check_columns(data)

        record = session.get(Character, character_id)
        if record is None:
            raise ValueError(f"id={character_id} という人物が見つからない")

        for key, value in data.items():
            setattr(record, key, value)
        return to_dict(record)
