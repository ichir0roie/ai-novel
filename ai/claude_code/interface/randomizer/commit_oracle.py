#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code.interface.randomizer._base import CommitMemeSource
from db.schema import Oracle
from db.schema_pydantic import to_dict


class CommitOracle(CommitMemeSource):
    model = Oracle

    def __init__(self, oracle: str | dict):
        self.oracle = oracle

    def execute(self, session) -> dict:
        data = self.parse(self.oracle)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("text"):
            raise ValueError("text は必須")

        record = Oracle(**data)
        session.add(record)
        self.finalize(session, record)
        return to_dict(record)
