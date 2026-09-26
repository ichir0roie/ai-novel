#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code.interface._base import Entrypoint
from tool.markdown.sync_db import WORLDS_ROOT, sync_db as _sync_db

__all__ = ["SyncDb"]


class SyncDb(Entrypoint):
    def __init__(self, root: str = WORLDS_ROOT):
        self.root = root

    def run(self) -> dict:
        return _sync_db(self.root)
