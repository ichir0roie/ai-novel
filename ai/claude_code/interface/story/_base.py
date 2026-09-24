#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code.interface._base import CommitEntrypoint, SessionEntrypoint


class StoryQuery(SessionEntrypoint):
    pass


class StoryCommit(CommitEntrypoint):
    pass
