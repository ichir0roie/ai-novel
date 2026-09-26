#!/usr/bin/env python3
"""アイデア `source_id`(主に候補)を `target_id` へまとめる、claude が呼ぶ入口。

`source_id` に結んであった出来事・話・人物と、`source_id` の呼び名は `target_id` へ付け替え、`source_id` は消す。
"""
from __future__ import annotations

from sqlalchemy import select

from ai.claude_code.interface._base import UnknownRecordError
from ai.claude_code.interface.randomizer._base import CommitDraft
from ai.time_keeper import idea_context
from db.schema import Idea


class MergeIdea(CommitDraft):
    model = Idea

    def __init__(self, source_id: int, target_id: int):
        self.source_id = int(source_id)
        self.target_id = int(target_id)

    def execute(self, session) -> dict:
        if self.source_id == self.target_id:
            raise ValueError("source_id と target_id が同じ")
        source = session.get(Idea, self.source_id)
        target = session.get(Idea, self.target_id)
        for label, record, id_ in (("source_id", source, self.source_id), ("target_id", target, self.target_id)):
            if record is None:
                raise UnknownRecordError(f"{label}={id_} という id の idea が見つからない")
        if session.scalars(select(Idea.id).where(Idea.parent_idea_id == source.id)).first() is not None:
            raise ValueError(f"source_id={self.source_id} には下位のアイデアが残っている。先に繋ぎ直す")

        aliases = session.scalars(select(Idea).where(Idea.alias_of_idea_id == source.id)).all()
        if aliases and target.alias_of_idea_id is not None:
            raise ValueError(f"source_id={self.source_id} には呼び名があり、target_id={self.target_id} は呼び名。"
                             "本質のアイデアへまとめる")
        for alias in aliases:
            alias.alias_of_idea_id = target.id
        moved = idea_context.relink(session, source.id, target.id)
        data = {"merged": {"id": source.id, "name": source.name, "kind": source.kind},
                "into": {"id": target.id, "name": target.name, "kind": target.kind},
                "links_moved": moved}
        session.delete(source)
        return data
