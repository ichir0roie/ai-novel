#!/usr/bin/env python3
"""db を `worlds/` の下へ md として書き出す、claude が呼ぶ入口。呼ぶたびに `worlds/` をまるごと消してから書き直す。

    ExportDb().run()   書き出した件数を、テーブル名ごとの辞書で返す
"""
from __future__ import annotations

from DEM.ai.claude_code.claude_interface._base import Entrypoint
from DEM.tool.markdown.export_db import WORLDS_ROOT, ExportError, export_db as _export_db

__all__ = ["ExportDb", "ExportError"]


class ExportDb(Entrypoint):
    """db を md へ書き出して、テーブル名ごとの件数を辞書で返す。"""

    def __init__(self, root: str = WORLDS_ROOT):
        self.root = root

    def run(self) -> dict[str, int]:
        return _export_db(self.root)
