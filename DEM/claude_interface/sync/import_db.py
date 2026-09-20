#!/usr/bin/env python3
"""`worlds/` の md を db へ読み戻す、claude が呼ぶ入口。`export_db.py` の逆。

`DEM.tool.markdown.import_db` の薄いラッパー。**db が本体で、`worlds/` は
その写し。** md を手で直してからここを呼ぶと、その内容が db に反映される
(id が既にあれば上書き、無ければ新規に作る)。テーブル名は置き場所
(`worlds/{table_name}/`)から読み、列の値は各ファイルの `# data` の json
から読む。

    ImportDb().run()   読み込んだ件数を、テーブル名ごとの辞書で返す
"""
from __future__ import annotations

from DEM.claude_interface._base import Entrypoint
from DEM.tool.markdown.import_db import WORLDS_ROOT, ImportDbError, import_db as _import_db

__all__ = ["ImportDb", "ImportDbError"]


class ImportDb(Entrypoint):
    """md を db へ読み戻して、テーブル名ごとの件数を辞書で返す。"""

    def __init__(self, root: str = WORLDS_ROOT):
        self.root = root

    def run(self) -> dict[str, int]:
        return _import_db(self.root)
