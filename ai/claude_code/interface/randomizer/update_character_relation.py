#!/usr/bin/env python3
"""既にある人物同士の相関を一件、渡した欄だけ db 上で直す、claude が呼ぶ入口。"""
from __future__ import annotations

from ai.claude_code.interface.randomizer._base import CommitDraft
from db.schema import Character, CharacterRelation
from db.schema_pydantic import to_dict


class UpdateCharacterRelation(CommitDraft):
    model = CharacterRelation

    def __init__(self, relation: str | dict):
        self.relation = relation

    def execute(self, session) -> dict:
        data = self.parse(self.relation)
        relation_id = data.pop("id", None)
        if relation_id is None:
            raise ValueError("id は必須(直す対象の相関)")
        self.check_columns(data)

        record = session.get(CharacterRelation, relation_id)
        if record is None:
            raise ValueError(f"id={relation_id} という人物の相関が見つからない")
        for key in ("character_id_1", "character_id_2"):
            self.check_exists(session, Character, data.get(key), key)

        for key, value in data.items():
            setattr(record, key, value)
        if record.character_id_1 == record.character_id_2:
            raise ValueError("character_id_1 と character_id_2 は別の人物")
        self.finalize(session, record)
        return to_dict(record)
