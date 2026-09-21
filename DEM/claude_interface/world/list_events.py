#!/usr/bin/env python3
"""出来事を全件、新しい順に見る、claude が呼ぶ入口。絞り込みは `ReadEvents` を使う。"""
from __future__ import annotations

from DEM.claude_interface.story._rows import event_row
from DEM.claude_interface.world._base import WorldQuery
from DEM.data_access_logic.query import common_query


class ListEvents(WorldQuery):
    def execute(self, session) -> list[dict]:
        rows = session.scalars(common_query.events_select()).all()
        return [event_row(row) for row in rows]
