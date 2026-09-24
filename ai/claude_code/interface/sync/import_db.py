#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code.interface._base import Entrypoint
from tool.markdown.import_db import WORLDS_ROOT, ImportDbError, import_db as _import_db

__all__ = ["ImportDb", "ImportDbError"]


class ImportDb(Entrypoint):
    def __init__(self, root: str = WORLDS_ROOT):
        self.root = root

    def run(self) -> dict[str, int]:
        return _import_db(self.root)
