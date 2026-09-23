#!/usr/bin/env python3
"""話を一件、db へ確定する、claude が呼ぶ入口。同じ作品の同じ話数があれば上書きする。

    CommitEpisode({"story_id": 1, "number": 6, "title": "…", "key": "…"}).run()   種だけ
    CommitEpisode({"story_id": 1, "number": 6, "title": "…", "text": "…"}).run()  本文
"""
from __future__ import annotations

from sqlalchemy import select

from DEM.ai.claude_code.interface.story._base import StoryCommit
from DEM.db.schema import Episode, Story
from DEM.db.schema_pydantic import to_dict


class CommitEpisode(StoryCommit):
    model = Episode

    def __init__(self, episode: str | dict):
        self.episode = episode

    def execute(self, session) -> dict:
        data = self.parse(self.episode)
        data.pop("id", None)
        data.pop("synced", None)
        self.check_columns(data)
        for required in ("story_id", "number"):
            if data.get(required) in (None, ""):
                raise ValueError(f"{required} は必須")
        if data.get("key") in (None, "") and data.get("text") in (None, ""):
            raise ValueError("key(種)か text(本文)のどちらかは必須")

        data["number"] = int(data["number"])
        data.setdefault("key", "")
        data.setdefault("text", "")
        data["letters"] = len(str(data["text"]))
        data.setdefault("title", "")

        self.check_exists(session, Story, data["story_id"], "story_id")
        record = session.scalars(
            select(Episode).where(Episode.story_id == data["story_id"],
                                  Episode.number == data["number"])).first()
        if record is None:
            record = Episode(synced=False, **data)
            session.add(record)
        else:
            for key, value in data.items():
                setattr(record, key, value)
            record.synced = False
        self.finalize(session, record)
        return to_dict(record)
