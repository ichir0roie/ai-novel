#!/usr/bin/env python3
"""db を `worlds/` の下へ md として書き出す、claude が呼ぶ入口。呼ぶたびに `worlds/` をまるごと消してから書き直す。

    ExportDb().run()              書き出した件数を、テーブル名ごとの辞書で返す
    ExportDb(force=True).run()    手で直した md を捨ててよいと分かっているときだけ

前回の同期より後に手で直された md があれば、書き出す前に止まる。
db 側を直したあとは、`ImportDb` を挟まずにこれだけを呼ぶ(挟むと、その変更が
md 側の古い内容で消える)。
"""
from __future__ import annotations

from DEM.ai.claude_code.interface._base import Entrypoint
from DEM.tool.markdown.export_db import WORLDS_ROOT, ExportError, export_db as _export_db
from DEM.tool.markdown.sync_stamp import edited_since_sync

__all__ = ["ExportDb", "ExportError"]

_SHOW_LIMIT = 5


class ExportDb(Entrypoint):
    """db を md へ書き出して、テーブル名ごとの件数を辞書で返す。"""

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
