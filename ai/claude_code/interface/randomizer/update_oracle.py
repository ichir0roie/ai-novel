#!/usr/bin/env python3
"""既にある oracle(著者の覚え書き)を一件、渡した欄だけ db 上で直す、claude が呼ぶ入口。"""
from __future__ import annotations

from ai.claude_code.interface._base import UnknownRecordError
from ai.claude_code.interface.randomizer._base import CommitDraft
from db.schema import Oracle
from db.schema_pydantic import to_dict


class UpdateOracle(CommitDraft):
    model = Oracle

    def __init__(self, oracle: str | dict):
        self.oracle = oracle

    def execute(self, session) -> dict:
        data = self.parse(self.oracle)
        oracle_id = data.pop("id", None)
        if oracle_id is None:
            raise ValueError("id は必須(直す対象の oracle)")
        self.check_columns(data)
        if "text" in data and not data["text"]:
            raise ValueError("text を空にはできない")

        record = session.get(Oracle, oracle_id)
        if record is None:
            raise UnknownRecordError(f"id={oracle_id} という oracle が見つからない")

        for key, value in data.items():
            setattr(record, key, value)
        self.finalize(session, record)
        return to_dict(record)
