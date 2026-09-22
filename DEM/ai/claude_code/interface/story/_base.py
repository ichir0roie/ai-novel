#!/usr/bin/env python3
"""`story/` 配下の入口に共通する基底。"""
from __future__ import annotations

from DEM.ai.claude_code.claude_interface._base import CommitEntrypoint, SessionEntrypoint


class StoryQuery(SessionEntrypoint):
    pass


class StoryCommit(CommitEntrypoint):
    pass
