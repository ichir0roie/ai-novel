#!/usr/bin/env python3
"""人物の情動(`CharacterDrive`)を一件、db へ確定する、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Character, CharacterDrive
from DEM.db.schema_pydantic import to_dict


class CommitCharacterDrive(CommitDraft):
    model = CharacterDrive

    def __init__(self, drive: str | dict):
        self.drive = drive

    def execute(self, session) -> dict:
        data = self.parse(self.drive)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("text"):
            raise ValueError("text は必須")
        if data.get("character_id") is None:
            raise ValueError("character_id は必須")

        self.check_exists(session, Character, data.get("character_id"), "character_id")

        record = CharacterDrive(**data)
        session.add(record)
        session.commit()
        return to_dict(record)
