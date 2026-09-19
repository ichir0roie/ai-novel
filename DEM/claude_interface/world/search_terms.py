#!/usr/bin/env python3
"""**語をキーワードで検索する**、claude が呼ぶ入口。

`term.text`（本文）にそのキーワードを含む語を一覧で返す。db には書き込まない。

CLI としても呼べる:
    python3 -m DEM.claude_interface.world.search_terms <キーワード>
"""
from __future__ import annotations

import json
import sys

from DEM.data_access_logic.query import dictionary_query
from DEM.db.schema import get_session


def search_terms(keyword: str) -> list[dict]:
    """語をキーワードで検索して返す。db には書き込まない。"""
    with get_session() as session:
        rows = session.scalars(dictionary_query.terms_by_keyword_select(keyword)).all()
        return [{"id": row.id, "name": row.name, "kind": row.kind,
                 "parent_term_id": row.parent_term_id, "text": row.text} for row in rows]


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    print(json.dumps(search_terms(arg), ensure_ascii=False, indent=2))
