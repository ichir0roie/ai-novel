#!/usr/bin/env python3
"""語(`Term`)を一件、db へ確定する、claude が呼ぶ入口。"""
from __future__ import annotations

from DEM.ai.claude_code.interface.randomizer._base import CommitDraft
from DEM.db.schema import Location, Term
from DEM.db.schema_pydantic import to_dict


class CommitTerm(CommitDraft):
    model = Term

    def __init__(self, term: str | dict):
        self.term = term

    def execute(self, session) -> dict:
        data = self.parse(self.term)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("name"):
            raise ValueError("name は必須")
        if not data.get("kind"):
            raise ValueError("kind は必須")
        data.setdefault("text", "")

        for column in ("restrict_world_id", "restrict_planet_id", "restrict_place_id"):
            self.check_exists(session, Location, data.get(column), column)
        self.check_exists(session, Term, data.get("parent_term_id"), "parent_term_id")

        record = Term(**data)
        session.add(record)
        self.finalize(session, record)
        return to_dict(record)
