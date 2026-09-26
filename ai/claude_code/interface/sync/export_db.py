#!/usr/bin/env python3
"""db と食い違う md だけを書き直す。手で直された md が残っていれば止まるので、ふだんは `SyncDb` を使う。"""
from __future__ import annotations

from ai.claude_code.interface._base import Entrypoint
from tool.markdown.export_db import WORLDS_ROOT, ExportError, export_db as _export_db

__all__ = ["ExportDb", "ExportError"]


class ExportDb(Entrypoint):
    def __init__(self, root: str = WORLDS_ROOT, force: bool = False):
        self.root = root
        self.force = force

    def run(self) -> dict[str, int]:
        return _export_db(self.root, force=self.force)
