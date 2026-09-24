#!/usr/bin/env python3
"""洗い出した語をアイデアと照らす、claude が呼ぶ入口(中間段を claude が自分で回すとき)。

    ResolveTerms([{"keyword": "虫憑き", "variants": ["寄生", "宿り"], "description": "…"}], place_id=61).run()

当たったアイデアとその上位・下位を `ideas` に返す。どれにも当たらなかった語は種別「候補」の
アイデアとして足し、`candidates` に返す(候補は `ideas` には出さない)。
清書したら `idea.link_ideas.LinkIdeas` で、`hits` と `candidates` の id を清書したレコードに結ぶ。
"""
from __future__ import annotations

from ai.claude_code.interface._base import CommitEntrypoint
from ai.time_keeper import idea_context
from db.schema import Idea


def _row(idea: Idea) -> dict:
    return {"id": idea.id, "name": idea.name, "kind": idea.kind,
            "parent_idea_id": idea.parent_idea_id, "text": idea.text}


class ResolveTerms(CommitEntrypoint):
    model = Idea

    def __init__(self, terms, place_id: int | None = None):
        self.terms = terms
        self.place_id = None if place_id is None else int(place_id)

    def execute(self, session) -> dict:
        context = idea_context.resolve(session, self.terms, self.place_id)
        return {"ideas": [_row(idea) for idea in context.related],
                "hits": [idea.id for idea in context.hits],
                "candidates": [_row(idea) for idea in context.candidates]}
