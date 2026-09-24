#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code.interface.story._rows import event_row
from ai.claude_code.interface.world._base import WorldQuery
from data_access_logic.query import common_query


class ListEvents(WorldQuery):
    def execute(self, session) -> list[dict]:
        rows = session.scalars(common_query.events_select()).all()
        return [event_row(row) for row in rows]
