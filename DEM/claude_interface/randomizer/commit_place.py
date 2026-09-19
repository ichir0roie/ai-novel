#!/usr/bin/env python3
"""JSON で受け取った場所を一件、db へ確定する、claude が呼ぶ入口。

`CreateRandomPlace` が返した辞書を claude が手順で決めた固有名詞・本文・
`parent_id` で書き換えたものを受け取る想定。db に触れるのはこのモジュールだけ
——`create_random_place` 側は一切 db を見ない。

実在レコードを指す欄（`parent_id`）は、渡された id が db に実在するかを
ここで確かめてから書き込む。`name` `kind` は必須。スキーマに無い欄が
混じっていたら（`DEM/db/schema.py` の `Location` の列と照らして）そこで止める。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Location
from DEM.db.schema_pydantic import to_dict


class CommitPlace(CommitDraft):
    """場所を一件、db へ確定して、格納後の中身を辞書で返す。

    `place` は JSON 文字列でも辞書でもよい。`id` キーは無視する
    （採番は db に任せる）。
    """

    model = Location

    def __init__(self, place: str | dict):
        self.place = place

    def execute(self, session) -> dict:
        data = self.parse(self.place)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("name"):
            raise ValueError("name は必須")
        if not data.get("kind"):
            raise ValueError("kind は必須")

        self.check_exists(session, Location, data.get("parent_id"), "parent_id")

        record = Location(**data)
        session.add(record)
        session.commit()
        return to_dict(record)
