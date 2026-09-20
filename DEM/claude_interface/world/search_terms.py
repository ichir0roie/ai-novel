#!/usr/bin/env python3
"""**語をキーワードで検索する**、claude が呼ぶ入口。

`term.text`(本文)にそのキーワードを含む語を一覧で返す。db には書き込まない。
"""
from __future__ import annotations

from DEM.claude_interface.world._base import WorldQuery
from DEM.data_access_logic.query import dictionary_query


class SearchTerms(WorldQuery):
    """語をキーワードで検索して返す。db には書き込まない。"""

    def __init__(self, keyword: str):
        self.keyword = keyword

    def select(self):
        return dictionary_query.terms_by_keyword_select(self.keyword)

    def row(self, row) -> dict:
        return {"id": row.id, "name": row.name, "kind": row.kind,
                "parent_term_id": row.parent_term_id, "text": row.text}
