#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code import ai_client
from ai.claude_code.interface._base import UnknownRecordError
from ai.claude_code.interface.randomizer._base import CommitDraft
from ai.time_keeper import generated_content
from db.schema import Event, Location, get_env_session
from db.schema_pydantic import to_dict


class UpdateEvent(CommitDraft):
    model = Event

    def __init__(self, event: str | dict):
        self.event = event

    def execute(self, session) -> dict:
        data = self.parse(self.event)
        event_id = data.pop("id", None)
        if event_id is None:
            raise ValueError("id は必須(直す対象の出来事)")
        self.check_columns(data)

        record = session.get(Event, event_id)
        if record is None:
            raise UnknownRecordError(f"id={event_id} という出来事が見つからない")

        if data.get("parent_event_id") == event_id:
            raise ValueError(f"parent_event_id={event_id} が自分自身を指している")
        self.check_exists(session, Event, data.get("parent_event_id"), "parent_event_id")
        self.check_exists(session, Location, data.get("location_id"), "location_id")

        for key, value in data.items():
            setattr(record, key, value)
        self.finalize(session, record)
        return to_dict(record)

    def run(self) -> dict:
        result = super().run()
        with get_env_session() as session:
            generated_content.refresh(session, ai_client, session.get(Event, result["id"]))
        return result
