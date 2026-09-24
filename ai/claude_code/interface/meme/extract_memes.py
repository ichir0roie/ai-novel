#!/usr/bin/env python3
"""アイデア(idea)・oracle(著者の覚え書き)・人物の筋書き(plot)・出来事(event)からミームを抜き出し、`meme` テーブルへ足す、claude が呼ぶ入口。

    ExtractMemes().run()   足したミームの件数を返す

足したミームは、AI にネット検索で中身を検めさせ、妥当性と補足を `review` 欄へ書く(`review=False` で飛ばす)。
"""
from __future__ import annotations

from sqlalchemy import func, select

from ai.claude_code import ai_client, reviewer
from ai.claude_code.interface._base import Entrypoint
from ai.time_keeper import meme as _meme
from db.schema import Meme, get_env_session

__all__ = ["ExtractMemes"]


class ExtractMemes(Entrypoint):
    """まだ抜き出していないアイデア・oracle・人物の筋書き・出来事からミームを抜き出す。足した件数を返す。"""

    def __init__(self, review: bool = True):
        self.review = review

    def run(self) -> int:
        with get_env_session() as session:
            last_id = session.scalar(select(func.max(Meme.id))) or 0
            added = _meme.refresh(session, ai_client)
            if self.review:
                new_ids = list(session.scalars(select(Meme.id).where(Meme.id > last_id)).all())
                if new_ids:
                    reviewer.review(session, "meme", ids=new_ids)
            return added
