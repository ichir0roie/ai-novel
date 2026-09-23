#!/usr/bin/env python3
"""作品(`Story`)を一件、db へ確定する、claude が呼ぶ入口。

    CommitStory({"name": "…", "place_id": 2, "narration": "三人称", "state": "構想中"}).run()
"""
from __future__ import annotations

from DEM.ai.claude_code.interface.story._base import StoryCommit
from DEM.db.schema import Location, Story
from DEM.db.schema_pydantic import to_dict


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
