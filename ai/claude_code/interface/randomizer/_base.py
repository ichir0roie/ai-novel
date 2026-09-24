#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code.interface._base import CommitEntrypoint, Entrypoint


class RandomDraft(Entrypoint):
    builder: staticmethod

    def __init__(self, **overrides):
        self.overrides = overrides

    def run(self) -> dict:
        return self.builder(**self.overrides)


class CommitDraft(CommitEntrypoint):
    pass
