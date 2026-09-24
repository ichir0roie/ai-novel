#!/usr/bin/env python3
"""`ImportDb` → db 側の変更 → これ、の順で呼ぶ(変更のあとに `ImportDb` を挟むと、
その変更が md 側の古い内容で消える)。
"""
from __future__ import annotations

from ai.claude_code.interface._base import Entrypoint
from tool.markdown.export_db import WORLDS_ROOT, ExportError, export_db as _export_db
from tool.markdown.sync_stamp import edited_since_sync

__all__ = ["ExportDb", "ExportError"]

_SHOW_LIMIT = 5


class ExportDb(Entrypoint):
    def __init__(self, root: str = WORLDS_ROOT, force: bool = False):
        self.root = root
        self.force = force

    def run(self) -> dict[str, int]:
        if not self.force:
            self.check_no_hand_edits()
        return _export_db(self.root)

    def check_no_hand_edits(self) -> None:
        edited = edited_since_sync(self.root)
        if not edited:
            return
        shown = "\n".join(edited[:_SHOW_LIMIT])
        rest = len(edited) - _SHOW_LIMIT
        if rest > 0:
            shown += f"\n(ほか {rest} 件)"
        raise ExportError(
            "前回の同期より後に手で直された md がある。書き出すと消える:\n"
            f"{shown}\n"
            "ImportDb() で取り込んでから、db 側の変更をやり直して ExportDb() を呼ぶ。"
            "md を捨ててよいなら ExportDb(force=True)。")
