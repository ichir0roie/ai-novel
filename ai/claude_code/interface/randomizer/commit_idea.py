#!/usr/bin/env python3
"""アイデア(`Idea`)を一件、db へ確定する、claude が呼ぶ入口。

確定したあと、AI にネット検索で中身を検めさせ、妥当性と補足を `review` 欄へ書く(`review=False` で飛ばす)。
検められなかったときは空のまま残り、`review.review_records.ReviewRecords("idea")` で後から埋める。
"""
from __future__ import annotations

from ai.claude_code.interface.randomizer._base import CommitDraft
from ai.claude_code.interface.review.review_records import ReviewRecords
from db.schema import Idea, Location, get_env_session
from db.schema_pydantic import to_dict


class CommitIdea(CommitDraft):
    model = Idea

    def __init__(self, idea: str | dict, review: bool = True):
        self.idea = idea
        self.review = review

    def run(self) -> dict:
        result = super().run()
        if self.review and result["text"].strip():
            ReviewRecords("idea", ids=[result["id"]]).run()
            with get_env_session() as session:
                result = to_dict(session.get(Idea, result["id"]))
        return result

    def execute(self, session) -> dict:
        data = self.parse(self.idea)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("name"):
            raise ValueError("name は必須")
        if not data.get("kind"):
            raise ValueError("kind は必須")
        data.setdefault("text", "")

        for column in ("restrict_world_id", "restrict_planet_id", "restrict_place_id"):
            self.check_exists(session, Location, data.get(column), column)
        self.check_exists(session, Idea, data.get("parent_idea_id"), "parent_idea_id")

        record = Idea(**data)
        session.add(record)
        self.finalize(session, record)
        return to_dict(record)
