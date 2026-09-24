#!/usr/bin/env python3
"""アイデアをキーワードで検索する、claude が呼ぶ入口。`idea.text` にそのキーワードを含むアイデアを返す。"""
from __future__ import annotations

from ai.claude_code.interface.world._base import WorldQuery
from data_access_logic.query import dictionary_query


class SearchIdeas(WorldQuery):
    def __init__(self, keyword: str):
        self.keyword = keyword

    def select(self):
        return dictionary_query.ideas_by_keyword_select(self.keyword)

    def row(self, row) -> dict:
        return {"id": row.id, "name": row.name, "kind": row.kind,
                "parent_idea_id": row.parent_idea_id, "text": row.text}
