#!/usr/bin/env python3
"""**同期フラグの下りている話を並べる**、claude が呼ぶ入口（モード 2-0）。

その話で起きたことが台帳へ戻っていない話が残っているあいだ、次の話の
材料（断面・顔ぶれ）は一話ぶん古い。**一件でも出たら、モード 2 をいったん
置いてモード 3 をやる。**

CLI としても呼べる:
    python3 -m DEM.claude_interface.story.list_unsynced_episodes [作品id]
"""
from __future__ import annotations

import json
import sys

from DEM.data_access_logic import query
from DEM.db.schema import get_session


def list_unsynced_episodes(story_id: int | None = None) -> list[dict]:
    """未同期の話を返す。空なら次の話へ進んでよい。"""
    with get_session() as session:
        return query.unsynced_episodes(
            session, None if story_id is None else int(story_id))


if __name__ == "__main__":
    story_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print(json.dumps(list_unsynced_episodes(story_id), ensure_ascii=False, indent=2))
