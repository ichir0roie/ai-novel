#!/usr/bin/env python3
"""アイデアをあいまい検索する、claude が呼ぶ入口。候補(種別「候補」)は返さない。

    SearchIdeas("霊纏").run()
    SearchIdeas([{"keyword": "遺伝子異常", "variants": ["遺伝病", "血の病", "遺伝"]}], place_id=58).run()

名前か本文に、キーワードか言い換えのどれかを含むアイデアを、当たり方の強い順に返す。
"""
from __future__ import annotations

from ai.claude_code.interface._base import SessionEntrypoint
from ai.time_keeper import idea_search


class SearchIdeas(SessionEntrypoint):
    def __init__(self, keywords, place_id: int | None = None, limit: int | None = None):
        self.keywords = keywords
        self.place_id = None if place_id is None else int(place_id)
        self.limit = limit

    def execute(self, session) -> list[dict]:
        return [
            {"id": hit.idea.id, "name": hit.idea.name, "kind": hit.idea.kind,
             "parent_idea_id": hit.idea.parent_idea_id, "text": hit.idea.text,
             "score": hit.score, "keywords": hit.keywords}
            for hit in idea_search.search(session, self.keywords, self.place_id, limit=self.limit)]
