#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code import ai_client
from ai.claude_code.interface._base import Entrypoint
from ai.time_keeper import meme as _meme
from db.schema import get_env_session

__all__ = ["ExtractMemes"]


class ExtractMemes(Entrypoint):
    def run(self) -> int:
        with get_env_session() as session:
            return _meme.refresh(session, ai_client)
