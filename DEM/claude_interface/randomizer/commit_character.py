#!/usr/bin/env python3
"""JSON で受け取った人物を一件、db へ確定する、claude が呼ぶ入口。

`CreateRandomCharacter` が返した辞書を claude が文脈に合わせて書き換えた
ものを受け取る想定。db に触れるのはこのモジュールだけ——
`create_random_character` 側は一切 db を見ない。

実在レコードを指す欄（`kind_id` `root_place_name` `born_place_id`
`belong_id`）は、渡された id が db に実在するかをここで確かめてから書き込む。
`kind_id` は必須（種別なしの人物は作らない）。スキーマに無い欄が混じっていたら
（`DEM/db/schema.py` の `Character` の列と照らして）そこで止める。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Character, Kind, Location, Object
from DEM.db.schema_pydantic import to_dict


class CommitCharacter(CommitDraft):
    """人物を一件、db へ確定して、格納後の中身を辞書で返す。

    `character` は JSON 文字列でも辞書でもよい。`id` キーは無視する
    （採番は db に任せる）。
    """

    model = Character

    def __init__(self, character: str | dict):
        self.character = character

    def execute(self, session) -> dict:
        data = self.parse(self.character)
        data.pop("id", None)
        self.check_columns(data)
        if data.get("kind_id") is None:
            raise ValueError("kind_id は必須")

        self.check_exists(session, Kind, data.get("kind_id"), "kind_id")
        self.check_exists(session, Location, data.get("root_place_name"), "root_place_name")
        self.check_exists(session, Location, data.get("born_place_id"), "born_place_id")
        self.check_exists(session, Object, data.get("belong_id"), "belong_id")

        record = Character(**data)
        session.add(record)
        session.commit()
        return to_dict(record)
