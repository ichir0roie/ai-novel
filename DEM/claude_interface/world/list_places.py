#!/usr/bin/env python3
"""**場所の一覧**を出す、claude が呼ぶ入口。

`kind` を渡すとその種別（`"村"` 等）だけに絞る。人物・出来事を場所に
紐づけるとき、対象の場所の id をここで拾う。

CLI としても呼べる:
    python3 -m DEM.claude_interface.world.list_places 村
"""
from __future__ import annotations

import json
import sys

from DEM.data_access_logic import query
from DEM.db.schema import get_session


def list_places(kind: str | None = None) -> list[dict]:
    """場所を一覧で返す。db には書き込まない。"""
    with get_session() as session:
        return query.places(session, kind=kind)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(list_places(arg), ensure_ascii=False, indent=2))
