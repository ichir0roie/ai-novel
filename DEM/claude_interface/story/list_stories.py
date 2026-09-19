#!/usr/bin/env python3
"""**作品の一覧**を出す、claude が呼ぶ入口。

どの作品があるか、どの世界線のどこに立つか、何話まで書いたか、
未同期の話が残っていないか（`unsynced`）が一枚で分かる。
作品の id をここで拾って、以降の入口に渡す。

CLI としても呼べる:
    python3 -m DEM.claude_interface.story.list_stories
"""
from __future__ import annotations

import json

from DEM.data_access_logic import query
from DEM.db.schema import get_session


def list_stories() -> list[dict]:
    """作品を全件、見出しの辞書で返す。"""
    with get_session() as session:
        return query.stories(session)


if __name__ == "__main__":
    print(json.dumps(list_stories(), ensure_ascii=False, indent=2))
