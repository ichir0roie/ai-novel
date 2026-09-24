#!/usr/bin/env python3
from __future__ import annotations

from sqlalchemy import select

from ai.claude_code.interface._base import UnknownRecordError
from ai.claude_code.interface.randomizer._base import CommitDraft
from db.schema import Idea


class DeleteIdea(CommitDraft):
    model = Idea

    def __init__(self, idea_id: int):
        self.idea_id = idea_id

    def execute(self, session) -> dict:
        record = session.get(Idea, int(self.idea_id))
        if record is None:
            raise UnknownRecordError(f"idea_id={self.idea_id} という id の idea が見つからない")
        child = session.scalars(
            select(Idea.id).where(Idea.parent_idea_id == record.id)).first()
        if child is not None:
            raise ValueError(f"idea_id={self.idea_id} には下位のアイデアが残っている。先にそちらを消すか繋ぎ直す")

        data = {"id": record.id, "name": record.name, "kind": record.kind}
        session.delete(record)
        return data
