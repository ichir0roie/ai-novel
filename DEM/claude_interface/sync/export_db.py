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

CLI としても呼べる:
    python3 -m DEM.claude_interface.sync.export_db
書き出した件数を JSON で標準出力へ返す。
"""
from __future__ import annotations

import json

from DEM.data_access_logic.sync import WORLDS_ROOT, ExportError, export_db as _export_db

__all__ = ["export_db", "export_db_json", "ExportError"]


def export_db(root: str = WORLDS_ROOT) -> dict[str, int]:
    """db を md へ書き出して、テーブル名ごとの件数を辞書で返す。"""
    return _export_db(root)


def export_db_json(root: str = WORLDS_ROOT) -> str:
    """`export_db` の結果を JSON 文字列で返す（CLI 出力向け）。"""
    return json.dumps(export_db(root), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print(export_db_json())
