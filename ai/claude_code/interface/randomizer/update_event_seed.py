#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code.interface._base import UnknownRecordError
from ai.claude_code.interface.randomizer._base import CommitDraft
from db.schema import EventSeed
from db.schema_pydantic import to_dict


class UpdateEventSeed(CommitDraft):
    model = EventSeed

    def __init__(self, seed: str | dict):
        self.seed = seed

    def execute(self, session) -> dict:
        data = self.parse(self.seed)
        seed_id = data.pop("id", None)
        if seed_id is None:
            raise ValueError("id は必須(直す対象の出来事の種)")
        self.check_columns(data)

        record = session.get(EventSeed, seed_id)
        if record is None:
            raise UnknownRecordError(f"id={seed_id} という出来事の種が見つからない")

        for key, value in data.items():
            setattr(record, key, value)
        self.finalize(session, record)
        return to_dict(record)
