#!/usr/bin/env python3
"""db の `MarkdownBase` を継ぐテーブルを `worlds/` の下へ md として書き出す、
claude が呼ぶ入口。

`DEM.tool.markdown.export_db` の薄いラッパー。**db が本体で、`worlds/` は
その写し。** 写しを手で書き換えても db には戻らないので、直したいときは
db の側(`commit_*` の入口)を直してから、ここを呼び直す。

置き場所は `worlds/{table_name}/{directory_path}/{id}_{filename}.md`
(`filename` は各行が持つ列。空なら `{id}.md`。**テーブルが持つ `name` 列
などとは別物**——見やすさのためだけの飾りで、db 上の意味は持たない)。
`directory_path` も各行が持つ列(`worlds/{table_name}/` からの相対
ディレクトリパス)で、空ならテーブル直下にそのまま置く。どちらも作者が
整理・見やすさのために使う欄で、ツール側が自動で組み立てることはしない。
`parent_id` のような自己参照 FK は他の列と同じデータとして書き出すだけで、
置き場所には使わない。

**毎回 `worlds/` をまるごと消してから書き直す。** 中途半端に古い md が
残っているほうが紛らわしいため。ファイル名が重複するレコードがあれば
`ExportError` で止まる。

    ExportDb().run()   書き出した件数を、テーブル名ごとの辞書で返す
"""
from __future__ import annotations

from DEM.claude_interface._base import Entrypoint
from DEM.tool.markdown.export_db import WORLDS_ROOT, ExportError, export_db as _export_db

__all__ = ["ExportDb", "ExportError"]


class ExportDb(Entrypoint):
    """db を md へ書き出して、テーブル名ごとの件数を辞書で返す。"""

    def __init__(self, root: str = WORLDS_ROOT):
        self.root = root

    def run(self) -> dict[str, int]:
        return _export_db(self.root)
