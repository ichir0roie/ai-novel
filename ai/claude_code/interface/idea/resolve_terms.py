#!/usr/bin/env python3
"""洗い出した語をアイデアと照らす、claude が呼ぶ入口(中間段を claude が自分で回すとき)。

    ResolveTerms([{"keyword": "虫憑き", "variants": ["寄生", "宿り"], "description": "…", "kind": "呼称"}],
                 place_id=61, time="1200/04/01").run()

`time` は出来事の時刻。その時刻に効くアイデアだけを引く。
当たったアイデアとその上位・下位を `ideas` に返す。呼び名に当たったら本質のアイデアにそろえ、
その場所・時刻での作中の呼び名を `called` に付ける。どれにも当たらなかった語は、`kind` の種別で
自動生成(`auto_generated`)のアイデアとして足し、`candidates` に返す。足した候補は `time` から効く。
清書したら `idea.link_ideas.LinkIdeas` で、`hits` と `candidates` の id を清書したレコードに結ぶ。
"""
from __future__ import annotations

from ai.claude_code.interface._base import CommitEntrypoint
from ai.time_keeper import idea_alias, idea_context
from db.schema import Idea


def _row(idea: Idea, called: dict[int, Idea] | None = None) -> dict:
    return {"id": idea.id, "name": idea.name, "kind": idea.kind, "auto_generated": idea.auto_generated,
            "parent_idea_id": idea.parent_idea_id, "alias_of_idea_id": idea.alias_of_idea_id,
            "called": idea_alias.name_of(idea, called or {}), "text": idea.text}


class ResolveTerms(CommitEntrypoint):
    model = Idea

    def __init__(self, terms, place_id: int | None = None, time=None):
        self.terms = terms
        self.place_id = None if place_id is None else int(place_id)
        self.time = time

    def execute(self, session) -> dict:
        context = idea_context.resolve(session, self.terms, self.place_id, self.time)
        return {"ideas": [_row(idea, context.called) for idea in context.related],
                "hits": [idea.id for idea in context.hits],
                "candidates": [_row(idea) for idea in context.candidates]}
