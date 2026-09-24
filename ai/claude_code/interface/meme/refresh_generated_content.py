#!/usr/bin/env python3
"""ミーム・出来事の要約(`event_summary`)・話の概要(`episode_summary`)の取りこぼしをまとめて作る、claude が呼ぶ入口。

    RefreshGeneratedContent().run()   作った/直した件数を辞書で返す
"""
from __future__ import annotations

from ai.claude_code import ai_client
from ai.claude_code.interface._base import Entrypoint
from ai.time_keeper import generated_content
from db.schema import get_env_session

__all__ = ["RefreshGeneratedContent"]


class RefreshGeneratedContent(Entrypoint):
    """まだ無い・古いミーム/出来事の要約/話の概要をまとめて作り直す。件数を辞書で返す。"""

    def run(self) -> dict:
        with get_env_session() as session:
            return generated_content.refresh_all(session, ai_client)
