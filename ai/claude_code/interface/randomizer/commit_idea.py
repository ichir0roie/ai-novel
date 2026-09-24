#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code.interface.randomizer._base import CommitMemeSource
from db.schema import Idea, Location
from db.schema_pydantic import to_dict


class CommitIdea(CommitMemeSource):
    model = Idea

    def __init__(self, idea: str | dict):
        self.idea = idea

    def execute(self, session) -> dict:
        data = self.parse(self.idea)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("name"):
            raise ValueError("name は必須")
        if not data.get("kind"):
            raise ValueError("kind は必須")
        data.setdefault("text", "")

        for column in ("restrict_world_id", "restrict_planet_id", "restrict_place_id"):
            self.check_exists(session, Location, data.get(column), column)
        self.check_exists(session, Idea, data.get("parent_idea_id"), "parent_idea_id")

        record = Idea(**data)
        session.add(record)
        self.finalize(session, record)
        return to_dict(record)
