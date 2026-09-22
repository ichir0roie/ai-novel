#!/usr/bin/env python3
"""話の同期フラグを立てる／下ろす、claude が呼ぶ入口。

    SetEpisodeSynced(1, 6).run()               立てる
    SetEpisodeSynced(1, 6, False).run()        下ろす
"""
from __future__ import annotations

from sqlalchemy import select

from DEM.ai.claude_code.interface._base import UnknownRecordError
from DEM.ai.claude_code.interface.story._base import StoryCommit
from DEM.db.schema import Episode
from DEM.db.schema_pydantic import to_dict


class SetEpisodeSynced(StoryCommit):
    """その話の同期フラグを入れ替えて、入れ替えたあとの中身を返す。"""

    model = Episode

    def __init__(self, story_id: int, number: int, synced: bool = True):
        self.story_id = story_id
        self.number = number
        self.synced = synced

    def execute(self, session) -> dict:
        record = session.scalars(
            select(Episode).where(Episode.story_id == int(self.story_id),
                                  Episode.number == int(self.number))).first()
        if record is None:
            raise UnknownRecordError(
                f"作品 {self.story_id} に {self.number} 話が無い")
        record.synced = bool(self.synced)
        return to_dict(record)
