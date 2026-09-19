#!/usr/bin/env python3
"""**個体（群）の一覧**を出す、claude が呼ぶ入口。

人物の `belong_id`（所属）に渡す id をここで拾う。`kind` を渡すと
その種別の名前（例: `"集落"`）だけに絞る。db には書き込まない。

CLI としても呼べる:
    python3 -m DEM.claude_interface.world.list_objects 集落
"""
from __future__ import annotations

import json
import sys

from DEM.data_access_logic.query import common_query
from DEM.db.schema import get_session
from DEM.db.schema_pydantic import relation_names


def list_objects(kind: str | None = None) -> list[dict]:
    """個体（群）を一覧で返す。"""
    with get_session() as session:
        rows = session.scalars(common_query.objects_select(kind=kind)).all()
        return [{"id": row.id, "name": row.name, "kind_id": row.kind_id,
                 **relation_names(row, ["kind"])} for row in rows]


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(list_objects(arg), ensure_ascii=False, indent=2))
