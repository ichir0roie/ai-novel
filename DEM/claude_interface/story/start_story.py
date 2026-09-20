#!/usr/bin/env python3
"""**モード 2 の材料を一度に出す**、claude が呼ぶ入口(2-0 〜 2-3)。

同期の確認・作品の見出し・直前の話・断面・顔ぶれが、この一本で出る。
一件ずつ入口を呼ぶと、そのたびに db を開き直すことになるため、
書き始める前はここを通す。出す範囲を変えたいときだけ、個別の入口を使う。

**未同期の話があれば、そこで止まる**(`stopped` が立ち、材料は出ない)。
古い台帳の上で次の話を組み立てないため。読むだけで何も書かないときは
`skip_sync=True` で抜けられるが、これを付けて次の話を書かない。
"""
from __future__ import annotations

from DEM.claude_interface.story import _rows
from DEM.claude_interface.story._base import StoryQuery
from DEM.data_access_logic.query import common_query


class StartStory(StoryQuery):
    """その作品を書き始めるのに要る材料を、まとめて辞書で返す。"""

    def __init__(self, story_id: int, time=None, episodes: int = 10, count: int = 5,
                 reach: int = 60, levels: int = 1, skip_sync: bool = False):
        self.story_id = int(story_id)
        self.time = time
        self.episodes = episodes
        self.count = count
        self.reach = reach
        self.levels = levels
        self.skip_sync = skip_sync

    def execute(self, session) -> dict:
        story = common_query.get_story(session, self.story_id)
        unsynced = _rows.unsynced_episodes(session, self.story_id)
        result = {
            "story": _rows.story_digest(session, story),
            "unsynced": unsynced,
            "stopped": bool(unsynced) and not self.skip_sync,
        }
        if result["stopped"]:
            result["message"] = (
                "未同期の話が残っている。モード 3(世界観更新)を先に通して、"
                "set_episode_synced で同期フラグを立ててから書き始める")
            return result

        _, until = common_query.resolve_time(session, self.time, story)
        result["time"] = str(until)
        result["episodes"] = _rows.episodes(session, self.story_id, count=int(self.episodes))
        result["cast"] = _rows.cast(session, self.story_id, until, count=int(self.count),
                                    levels=int(self.levels))
        if story.place_id is not None:
            result["brief"] = _rows.brief(session, story.place_id, until,
                                          reach=int(self.reach))
        return result
