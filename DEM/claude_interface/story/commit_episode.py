#!/usr/bin/env python3
"""**話を一件、db へ確定する**、claude が呼ぶ入口(モード 2-4)。

本文は claude が書くので「作る」側の入口は無い。ここが db に触れる側。
同じ作品の同じ話数が既にあれば、その行を書き換える(話数を二重に作らない)。

字数(`letters`)は本文から数えて入れる。`synced` は**必ず下りた状態で入る**——
その話で起きたことを台帳へ戻すのはモード 3 の仕事で、戻し終えてから
`set_episode_synced` で立てる。

    CommitEpisode({"story_id": 1, "number": 6, "title": "…", "text": "…"}).run()
"""
from __future__ import annotations

from sqlalchemy import select

from DEM.claude_interface.story._base import StoryCommit
from DEM.db.schema import Episode, Story
from DEM.db.schema_pydantic import to_dict


class CommitEpisode(StoryCommit):
    """話を一件、db へ確定して、格納後の中身を辞書で返す。"""

    model = Episode

    def __init__(self, episode: str | dict):
        self.episode = episode

    def execute(self, session) -> dict:
        data = self.parse(self.episode)
        data.pop("id", None)
        data.pop("synced", None)
        self.check_columns(data)
        for required in ("story_id", "number", "text"):
            if data.get(required) in (None, ""):
                raise ValueError(f"{required} は必須")

        data["number"] = int(data["number"])
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
        session.commit()
        return to_dict(record)
