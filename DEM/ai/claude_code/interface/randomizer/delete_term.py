#!/usr/bin/env python3
"""語を一件、db から削除する、claude が呼ぶ入口。下位の語を持つ語は消せない。"""
from __future__ import annotations

from sqlalchemy import select

from DEM.ai.claude_code.interface._base import UnknownRecordError
from DEM.ai.claude_code.interface.randomizer._base import CommitDraft
from DEM.db.schema import Term


class DeleteTerm(CommitDraft):
    """語を一件削除して、消す直前の中身を辞書で返す。"""

    model = Term

    def __init__(self, term_id: int):
        self.term_id = term_id

    def execute(self, session) -> dict:
        record = session.get(Term, int(self.term_id))
        if record is None:
            raise UnknownRecordError(f"term_id={self.term_id} という id の term が見つからない")
        child = session.scalars(
            select(Term.id).where(Term.parent_term_id == record.id)).first()
        if child is not None:
            raise ValueError(f"term_id={self.term_id} には下位の語が残っている。先にそちらを消すか繋ぎ直す")

        data = {"id": record.id, "name": record.name, "kind": record.kind}
        session.delete(record)
        return data
