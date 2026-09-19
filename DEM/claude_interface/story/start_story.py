#!/usr/bin/env python3
"""**モード 2 の材料を一度に出す**、claude が呼ぶ入口（2-0 〜 2-3）。

同期の確認・作品の見出し・直前の話・断面・顔ぶれが、この一本で出る。
一件ずつ入口を呼ぶと、そのたびに db を開き直すことになるため、
書き始める前はここを通す。出す範囲を変えたいときだけ、個別の入口を使う。

**未同期の話があれば、そこで止まる**（`stopped` が立ち、材料は出ない）。
古い台帳の上で次の話を組み立てないため。読むだけで何も書かないときは
`skip_sync=True` で抜けられるが、これを付けて次の話を書かない。

CLI としても呼べる:
    python3 -m DEM.claude_interface.story.start_story <作品id> [時刻]
"""
from __future__ import annotations

import json
import sys

from DEM.claude_interface.story import _rows
from DEM.data_access_logic.query import common_query
from DEM.db.schema import get_session


def start_story(story_id: int, time=None, episodes: int = 10, count: int = 5,
                reach: int = 60, levels: int = 1, skip_sync: bool = False) -> dict:
    """その作品を書き始めるのに要る材料を、まとめて辞書で返す。"""
    story_id = int(story_id)
    with get_session() as session:
        story = common_query.get_story(session, story_id)
        unsynced = _rows.unsynced_episodes(session, story_id)
        result = {
            "story": _rows.story_digest(session, story),
            "unsynced": unsynced,
            "stopped": bool(unsynced) and not skip_sync,
        }
        if result["stopped"]:
            result["message"] = (
                "未同期の話が残っている。モード 3（世界観更新）を先に通して、"
                "set_episode_synced で同期フラグを立ててから書き始める")
            return result

        _, until = common_query.resolve_time(session, time, story)
        result["time"] = str(until)
        result["episodes"] = _rows.episodes(session, story_id, count=int(episodes))
        result["cast"] = _rows.cast(session, story_id, until, count=int(count),
                                    levels=int(levels))
        if story.place_id is not None:
            result["brief"] = _rows.brief(session, story.place_id, until,
                                          reach=int(reach))
        return result


if __name__ == "__main__":
    story_id = int(sys.argv[1])
    when = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(start_story(story_id, when), ensure_ascii=False, indent=2))
