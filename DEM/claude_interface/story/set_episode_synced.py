#!/usr/bin/env python3
"""**話の同期フラグを立てる／下ろす**、claude が呼ぶ入口（モード 3-3）。

その話で起きたことを台帳（場所・人物・個体・語）へ戻し終えてから立てる。
立てないまま次の話へ行くと、`start_story` が 2-0 で止まる。

    set_episode_synced(1, 6)              立てる
    set_episode_synced(1, 6, False)       下ろす

CLI としても呼べる:
    python3 -m DEM.claude_interface.story.set_episode_synced <作品id> <話数>
"""
from __future__ import annotations

import json
import sys

from sqlalchemy import select

from DEM.db.schema import Episode, get_session
from DEM.db.schema_pydantic import to_dict


class UnknownRecordError(ValueError):
    """指した話が db に無い。"""


def set_episode_synced(story_id: int, number: int, synced: bool = True) -> dict:
    """その話の同期フラグを入れ替えて、入れ替えたあとの中身を返す。"""
    with get_session() as session:
        record = session.scalars(
            select(Episode).where(Episode.story_id == int(story_id),
                                  Episode.number == int(number))).first()
        if record is None:
            raise UnknownRecordError(
                f"作品 {story_id} に {number} 話が無い")
        record.synced = bool(synced)
        session.commit()
        return to_dict(record)


if __name__ == "__main__":
    print(json.dumps(set_episode_synced(int(sys.argv[1]), int(sys.argv[2])),
                     ensure_ascii=False, indent=2))
