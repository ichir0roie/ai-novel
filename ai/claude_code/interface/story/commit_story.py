#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code import ai_client
from ai.claude_code.interface.story._base import StoryCommit
from ai.time_keeper import generated_content
from db.schema import Location, Story, get_env_session
from db.schema_pydantic import to_dict


class CommitStory(StoryCommit):
    model = Story

    def __init__(self, story: str | dict):
        self.story = story

    def execute(self, session) -> dict:
        data = self.parse(self.story)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("name"):
            raise ValueError("name は必須")
        data.setdefault("text", "")
        data.setdefault("narration", "")
        data.setdefault("state", "")

        self.check_exists(session, Location, data.get("world_id"), "world_id")
        self.check_exists(session, Location, data.get("place_id"), "place_id")

        record = Story(**data)
        session.add(record)
        self.finalize(session, record)
        return to_dict(record)

    def run(self) -> dict:
        result = super().run()
        with get_env_session() as session:
            generated_content.refresh(session, ai_client)
        return result
