#!/usr/bin/env python3
"""`world/` 配下の入口に共通する基底。"""
from __future__ import annotations

from DEM.claude_interface._base import SessionEntrypoint


class WorldQuery(SessionEntrypoint):
    """**場所・種別・個体・語を一覧・検索する入口の基底。** db には書き込まない。

    サブクラスは `select()`(`Select` を返す)と `row(row)`(一行を辞書に
    する)だけを用意すればよい。
    """

    def execute(self, session) -> list[dict]:
        rows = session.scalars(self.select()).all()
        return [self.row(row) for row in rows]

    def select(self):
        raise NotImplementedError

    def row(self, row) -> dict:
        raise NotImplementedError
