#!/usr/bin/env python3
"""作品(`Story`)を一件、db から削除する、claude が呼ぶ入口。

    DeleteStory(story_id).run()
"""
from __future__ import annotations

from sqlalchemy import select

from DEM.ai.claude_code.interface._base import UnknownRecordError
from DEM.ai.claude_code.interface.story._base import StoryCommit
from DEM.db.schema import Episode, Story


class DeleteStory(StoryCommit):
    """作品を一件削除して、消す直前の中身を辞書で返す。本文(`episode`)が残っていれば止める。"""

    model = Story

    def __init__(self, story_id: int):
        self.story_id = story_id

    def execute(self, session) -> dict:
        record = session.get(Story, int(self.story_id))
        if record is None:
            raise UnknownRecordError(
                f"story_id={self.story_id} という id の story が見つからない")

        episode_id = session.scalar(
            select(Episode.id).where(Episode.story_id == record.id).limit(1))
        if episode_id is not None:
            raise ValueError(
                f"story_id={record.id} にはまだ話が残っている。先に話を消してから削除する")

        data = {"id": record.id, "name": record.name, "place_id": record.place_id,
                "text": record.text}
        session.delete(record)
        return data
