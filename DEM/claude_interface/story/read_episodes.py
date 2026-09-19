#!/usr/bin/env python3
"""**直前の N 話を読む**、claude が呼ぶ入口（モード 2-1）。

展開を考える前にここを通す。前の話の引き・口調・終わり方を持たないまま
次を組み立てると、同じ場面をもう一度書くことになる。

    read_episodes(1)                 最新 10 話の本文
    read_episodes(1, before=15)      15 話の前 10 話
    read_episodes(1, count=50, text=False)   話数と題だけの一覧

CLI としても呼べる:
    python3 -m DEM.claude_interface.story.read_episodes <作品id> [話数]
"""
from __future__ import annotations

import json
import sys

from DEM.claude_interface.story import _rows
from DEM.db.schema import get_session


def read_episodes(story_id: int, count: int = 10, before: int | None = None,
                  text: bool = True) -> list[dict]:
    """その作品の話を古い順に返す。`text=False` なら話数と題だけ。"""
    with get_session() as session:
        return _rows.episodes(session, int(story_id), count=int(count),
                              before=before, text=text)


if __name__ == "__main__":
    story_id = int(sys.argv[1])
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    print(json.dumps(read_episodes(story_id, count), ensure_ascii=False, indent=2))
