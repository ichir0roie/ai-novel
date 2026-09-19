#!/usr/bin/env python3
"""**種別（系統）の一覧**を出す、claude が呼ぶ入口。

人物や個体の `kind_id` に渡す id をここで拾う。db には書き込まない。

CLI としても呼べる:
    python3 -m DEM.claude_interface.world.list_kinds
"""
from __future__ import annotations

import json

from DEM.data_access_logic import query
from DEM.db.schema import get_session


def list_kinds() -> list[dict]:
    """種別を一覧で返す。"""
    with get_session() as session:
        return query.kinds(session)


if __name__ == "__main__":
    print(json.dumps(list_kinds(), ensure_ascii=False, indent=2))
