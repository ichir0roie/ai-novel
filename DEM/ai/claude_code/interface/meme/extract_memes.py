#!/usr/bin/env python3
"""語(term)・oracle(著者の覚え書き)・人物の筋書き(plot)からミームを抜き出し、`meme` テーブルへ足す、claude が呼ぶ入口。

    ExtractMemes().run()   足したミームの件数を返す
"""
from __future__ import annotations

from DEM.ai.claude_code import ai_client
from DEM.ai.claude_code.interface._base import Entrypoint
from DEM.ai.time_keeper import meme as _meme
from DEM.db.schema import get_env_session

__all__ = ["ExtractMemes"]


class ExtractMemes(Entrypoint):
    """まだ抜き出していない語・oracle・人物の筋書きからミームを抜き出す。足した件数を返す。"""

    def run(self) -> int:
        with get_env_session() as session:
            return _meme.refresh(session, ai_client)
