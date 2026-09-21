#!/usr/bin/env python3
"""JSON で受け取った人物を一件、db へ確定する、claude が呼ぶ入口。

`CreateRandomCharacter` が返した辞書を claude が文脈に合わせて書き換えた
ものを受け取る想定。db に触れるのはこのモジュールだけ——
`create_random_character` 側は一切 db を見ない。

実在レコードを指す欄(`root_place_name` `born_place_id` `belong_id`)は、
渡された id が db に実在するかをここで確かめてから書き込む。スキーマに無い欄が
混じっていたら(`DEM/db/schema.py` の `Character` の列と照らして)そこで止める。

`born_place_id` を持つ場合は、その場所に出自を持つ人物が既に
`world_createion_query.MAX_PER_LOCATION`(10)件あれば止める。
また、`start`〜`end` が `born_place_id` の場所の `start`〜`end` に収まって
いるか(その場所がまだ無い時刻・既に終わった時刻に生まれていないか)も確かめる。
さらに、その場所(か祖先、か場所を問わない筋書き)にプロットが一件も無ければ
止める(`world_createion_query.check_has_plot`)。プロットの無いエリアに
展開の当てが無いまま人物だけが増えるのを防ぐ。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.data_access_logic.query import world_createion_query
from DEM.db.schema import Character, Location, Object
from DEM.db.schema_pydantic import to_dict


class CommitCharacter(CommitDraft):
    """人物を一件、db へ確定して、格納後の中身を辞書で返す。

    `character` は JSON 文字列でも辞書でもよい。`id` キーは無視する
    (採番は db に任せる)。
    """

    model = Character

    def __init__(self, character: str | dict):
        self.character = character

    def execute(self, session) -> dict:
        data = self.parse(self.character)
        data.pop("id", None)
        self.check_columns(data)

        self.check_exists(session, Location, data.get("root_place_name"), "root_place_name")
        self.check_exists(session, Location, data.get("born_place_id"), "born_place_id")
        self.check_exists(session, Object, data.get("belong_id"), "belong_id")
        self._check_capacity(session, data)
        self._check_span(session, data)
        self._check_plot(session, data)

        record = Character(**data)
        session.add(record)
        session.commit()
        return to_dict(record)

    @staticmethod
    def _check_capacity(session, data: dict) -> None:
        born_place_id = data.get("born_place_id")
        if born_place_id is None:
            return
        count = session.scalar(
            world_createion_query.character_count_at_place_select(born_place_id))
        if count >= world_createion_query.MAX_PER_LOCATION:
            raise ValueError(
                f"born_place_id={born_place_id} には既に人物が "
                f"{world_createion_query.MAX_PER_LOCATION} 件あり、これ以上作れない")

    @staticmethod
    def _check_span(session, data: dict) -> None:
        born_place_id = data.get("born_place_id")
        if born_place_id is None:
            return
        born_place = session.get(Location, born_place_id)
        world_createion_query.check_within_parent_span(
            born_place, data.get("start"), data.get("end"), "character")

    @staticmethod
    def _check_plot(session, data: dict) -> None:
        born_place_id = data.get("born_place_id")
        if born_place_id is None:
            return
        world_createion_query.check_has_plot(session, born_place_id, "character")
