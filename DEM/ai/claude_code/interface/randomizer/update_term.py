#!/usr/bin/env python3
"""既にある語を一件、渡した欄だけ db 上で直す、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.ai.claude_code.interface.randomizer._base import CommitDraft
from DEM.db.schema import Location, Term
from DEM.db.schema_pydantic import to_dict


class UpdateTerm(CommitDraft):
    model = Term

    def __init__(self, term: str | dict):
        self.term = term

    def execute(self, session) -> dict:
        data = self.parse(self.term)
        term_id = data.pop("id", None)
        if term_id is None:
            raise ValueError("id は必須(直す対象の語)")
        self.check_columns(data)

        record = session.get(Term, term_id)
        if record is None:
            raise ValueError(f"id={term_id} という語が見つからない")

        for column in ("restrict_world_id", "restrict_planet_id", "restrict_place_id"):
            self.check_exists(session, Location, data.get(column), column)
        if data.get("parent_term_id") == term_id:
            raise ValueError(f"parent_term_id={term_id} が自分自身を指している")
        self.check_exists(session, Term, data.get("parent_term_id"), "parent_term_id")

        for key, value in data.items():
            setattr(record, key, value)
        self.finalize(session, record)
        return to_dict(record)
