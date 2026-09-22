#!/usr/bin/env python3
"""`worlds/` の md を db へ読み戻す、claude が呼ぶ入口。`export_db.py` の逆。

    ImportDb().run()   読み込んだ件数を、テーブル名ごとの辞書で返す
"""
from __future__ import annotations

from DEM.ai.claude_code.interface._base import Entrypoint
from DEM.tool.markdown.import_db import WORLDS_ROOT, ImportDbError, import_db as _import_db

__all__ = ["ImportDb", "ImportDbError"]


class ImportDb(Entrypoint):
    """md を db へ読み戻して、テーブル名ごとの件数を辞書で返す。"""

    def __init__(self, root: str = WORLDS_ROOT):
        self.root = root

    def run(self) -> dict[str, int]:
        return _import_db(self.root)
