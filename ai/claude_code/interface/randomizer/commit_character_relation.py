#!/usr/bin/env python3
"""人物同士の相関(`CharacterRelation`)を一件、db へ確定する、claude が呼ぶ入口。"""
from __future__ import annotations

from ai.claude_code.interface.randomizer._base import CommitDraft
from db.schema import Character, CharacterRelation
from db.schema_pydantic import to_dict


class CommitCharacterRelation(CommitDraft):
    model = CharacterRelation

    def __init__(self, relation: str | dict):
        self.relation = relation

    def execute(self, session) -> dict:
        data = self.parse(self.relation)
        data.pop("id", None)
        self.check_columns(data)
        for key in ("character_id_1", "character_id_2", "relation"):
            if data.get(key) in (None, ""):
                raise ValueError(f"{key} は必須")
        if data["character_id_1"] == data["character_id_2"]:
            raise ValueError("character_id_1 と character_id_2 は別の人物")
        data.setdefault("text", "")

        self.check_exists(session, Character, data["character_id_1"], "character_id_1")
        self.check_exists(session, Character, data["character_id_2"], "character_id_2")

        record = CharacterRelation(**data)
        session.add(record)
        self.finalize(session, record)
        return to_dict(record)
