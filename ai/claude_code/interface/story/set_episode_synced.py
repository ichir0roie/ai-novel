#!/usr/bin/env python3
from __future__ import annotations

from sqlalchemy import select

from ai.claude_code.interface._base import UnknownRecordError
from ai.claude_code.interface.story._base import StoryCommit
from db.schema import Episode
from db.schema_pydantic import to_dict


class SetEpisodeSynced(StoryCommit):
    model = Episode

    def __init__(self, story_id: int, number: int, synced: bool = True):
        self.story_id = story_id
        self.number = number
        self.synced = synced

    def execute(self, session) -> dict:
        record = session.scalars(
            select(Episode).where(Episode.story_id == int(self.story_id),
                                  Episode.number == int(self.number))).first()
        if record is None:
            raise UnknownRecordError(
                f"作品 {self.story_id} に {self.number} 話が無い")
        record.synced = bool(self.synced)
        return to_dict(record)
