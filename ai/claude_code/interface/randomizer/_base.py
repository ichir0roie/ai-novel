#!/usr/bin/env python3
"""`randomizer/` 配下の入口に共通する基底。"""
from __future__ import annotations

from ai.claude_code.interface._base import CommitEntrypoint, Entrypoint


class RandomDraft(Entrypoint):
    """サブクラスは `builder` に生成関数を指す。`overrides` はそのまま渡る。"""

    builder: staticmethod

    def __init__(self, **overrides):
        self.overrides = overrides

    def run(self) -> dict:
        return self.builder(**self.overrides)


class CommitDraft(CommitEntrypoint):
    """作った下書きを db へ確定する、共通の基底。"""
