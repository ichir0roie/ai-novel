#!/usr/bin/env python3
"""**出来事(`Event`)を一覧で見る**、claude が呼ぶ入口。

db にある出来事を全件、新しい順に返す。絞り込みたいときは `ReadEvents`
(時刻か id で引く)を使う。db には触れない。
"""
from __future__ import annotations

from DEM.claude_interface.story._rows import event_row
from DEM.claude_interface.world._base import WorldQuery
from DEM.data_access_logic.query import common_query


class ListEvents(WorldQuery):
    """出来事を一覧で返す。db には書き込まない。"""

    def execute(self, session) -> list[dict]:
        rows = session.scalars(common_query.events_select()).all()
        return [event_row(row) for row in rows]
