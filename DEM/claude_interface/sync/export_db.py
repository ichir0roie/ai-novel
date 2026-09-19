#!/usr/bin/env python3
"""db の本文を `worlds/` の下へ md として書き出す、claude が呼ぶ入口。

`DEM.data_access_logic.sync.export_db` の薄いラッパー。**db が本体で、
`worlds/` はその写し。** 写しを手で書き換えても db には戻らないので、
直したいときは db の側（`commit_*` の入口）を直してから、ここを呼び直す。

置き場所は次のようになる:

```
worlds/location/<親…>/<場所>/<場所>.md
worlds/term/<親…>/<語>/<語>.md
worlds/kind/<種別>.md
worlds/skill/<技>.md
worlds/object/<個体>/<個体>.md
worlds/object/<個体>/events/<時刻>_<出来事>.md
worlds/character/<人物>/<人物>.md
worlds/character/<人物>/character_drive/<時刻>_<情動>.md
worlds/character/<人物>/events/<時刻>_<行動>.md
worlds/story/<作品>/<作品>.md
worlds/story/<作品>/episodes/<話数>.md
worlds/event/<時刻>_<出来事>.md   誰の行動でもない、ただ起きたこと
```

**毎回 `worlds/` をまるごと消してから書き直す。** 中途半端に古い md が
残っているほうが紛らわしいため。書き出せないレコードが一件でもあれば
（親を指す欄が実在しない id を指している等）`ExportError` で止まる。

    ExportDb().run()   書き出した件数を、テーブル名ごとの辞書で返す
"""
from __future__ import annotations

from DEM.claude_interface._base import Entrypoint
from DEM.data_access_logic.sync import WORLDS_ROOT, ExportError, export_db as _export_db

__all__ = ["ExportDb", "ExportError"]


class ExportDb(Entrypoint):
    """db を md へ書き出して、テーブル名ごとの件数を辞書で返す。"""

    def __init__(self, root: str = WORLDS_ROOT):
        self.root = root

    def run(self) -> dict[str, int]:
        return _export_db(self.root)
