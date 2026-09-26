#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code.interface.randomizer._base import CommitDraft
from ai.time_keeper import idea_alias
from db.schema import Idea, Location
from db.schema_pydantic import to_dict


class UpdateIdea(CommitDraft):
    model = Idea

    def __init__(self, idea: str | dict):
        self.idea = idea

    def execute(self, session) -> dict:
        data = self.parse(self.idea)
        idea_id = data.pop("id", None)
        if idea_id is None:
            raise ValueError("id は必須(直す対象のアイデア)")
        self.check_columns(data)

        record = session.get(Idea, idea_id)
        if record is None:
            raise ValueError(f"id={idea_id} というアイデアが見つからない")

        self.check_exists(session, Location, data.get("location_id"), "location_id")
        if data.get("parent_idea_id") == idea_id:
            raise ValueError(f"parent_idea_id={idea_id} が自分自身を指している")
        self.check_exists(session, Idea, data.get("parent_idea_id"), "parent_idea_id")
        idea_alias.check(session, idea_id, data.get("alias_of_idea_id"))

        for key, value in data.items():
            setattr(record, key, value)
        self.finalize(session, record)
        return to_dict(record)
