#!/usr/bin/env python3
"""アイデアを一件、db から削除する、claude が呼ぶ入口。下位のアイデアを持つアイデアは消せない。"""
from __future__ import annotations

from sqlalchemy import select

from DEM.ai.claude_code.interface._base import UnknownRecordError
from DEM.ai.claude_code.interface.randomizer._base import CommitDraft
from DEM.db.schema import Idea


class DeleteIdea(CommitDraft):
    """アイデアを一件削除して、消す直前の中身を辞書で返す。"""

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
