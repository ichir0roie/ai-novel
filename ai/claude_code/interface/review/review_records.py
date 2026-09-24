#!/usr/bin/env python3
"""アイデア・ミームの中身を AI にネット検索させて検め、妥当性と補足を `review` 欄(md の `# review` 節)へ書く、claude が呼ぶ入口。

    ReviewRecords("idea").run()              まだ検めていないアイデアをすべて検める
    ReviewRecords("meme", limit=10).run()    まだ検めていないミームを 10 件だけ検める
    ReviewRecords("idea", ids=[30]).run()    名指ししたものを検め直す
"""
from __future__ import annotations

from ai.claude_code import reviewer
from ai.claude_code.interface._base import Entrypoint
from db.schema import get_env_session

__all__ = ["ReviewRecords"]


class ReviewRecords(Entrypoint):
    """`table`("idea" / "meme")を検める。書いた件数を返す。"""

    def __init__(self, table: str, ids: list[int] | None = None, limit: int | None = None):
        if table not in reviewer.MODELS:
            raise ValueError(f"table は {'/'.join(reviewer.MODELS)} のいずれか: {table!r}")
        self.table = table
        self.ids = ids
        self.limit = limit

    def run(self) -> int:
        with get_env_session() as session:
            return reviewer.review(session, self.table, self.ids, self.limit)
