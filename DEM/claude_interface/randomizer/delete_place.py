#!/usr/bin/env python3
"""場所を一件、db から削除する、claude が呼ぶ入口。

生成したはいいが方針と食い違った下書き（誤って確定してしまった場所）を
取り消すためのもの。**配下に子の場所を持つ場所は消せない**（先に子を消すか
`parent_id` を付け替える）。出来事・語などから掛かられているかまでは
確かめない——消す前に、その id が本当に不要か呼び出し側が確認すること。
"""
from __future__ import annotations

from sqlalchemy import select

from DEM.claude_interface._base import UnknownRecordError
from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Location


class DeletePlace(CommitDraft):
    """場所を一件削除して、消す直前の中身を辞書で返す。"""

    model = Location

    def __init__(self, place_id: int):
        self.place_id = place_id

    def execute(self, session) -> dict:
        record = session.get(Location, int(self.place_id))
        if record is None:
            raise UnknownRecordError(
                f"place_id={self.place_id} という id の location が見つからない")
        child = session.scalars(
            select(Location.id).where(Location.parent_id == record.id)).first()
        if child is not None:
            raise ValueError(f"place_id={self.place_id} には子の場所が残っている。先にそちらを消す")

        data = {"id": record.id, "name": record.name, "kind": record.kind}
        session.delete(record)
        session.commit()
        return data
