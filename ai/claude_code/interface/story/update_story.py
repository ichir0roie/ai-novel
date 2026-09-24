#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code.interface.story._base import StoryCommit
from db.schema import Location, Story
from db.schema_pydantic import to_dict


class UpdateStory(StoryCommit):
    model = Story

    def __init__(self, story: str | dict):
        self.story = story

    def execute(self, session) -> dict:
        data = self.parse(self.story)
        story_id = data.pop("id", None)
        if story_id is None:
            raise ValueError("id は必須(直す対象の作品)")
        self.check_columns(data)

        record = session.get(Story, story_id)
        if record is None:
            raise ValueError(f"id={story_id} という作品が見つからない")

        self.check_exists(session, Location, data.get("world_id"), "world_id")
        self.check_exists(session, Location, data.get("place_id"), "place_id")

        for key, value in data.items():
            setattr(record, key, value)
        self.finalize(session, record)
        return to_dict(record)
