#!/usr/bin/env python3
"""`story/` 配下の入口に共通する基底。"""
from __future__ import annotations

from DEM.claude_interface._base import CommitEntrypoint, SessionEntrypoint


class StoryQuery(SessionEntrypoint):
    """モード 2 の材料を読む入口の基底。db には書き込まない。"""


class StoryCommit(CommitEntrypoint):
    """話（episode）を db へ確定する系の基底。"""
