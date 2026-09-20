#!/usr/bin/env python3
"""JSON で受け取った場所を一件、db へ確定する、claude が呼ぶ入口。

`CreateRandomPlace` が返した辞書を claude が手順で決めた固有名詞・本文・
`parent_id` で書き換えたものを受け取る想定。db に触れるのはこのモジュールだけ
——`create_random_place` 側は一切 db を見ない。

実在レコードを指す欄(`parent_id`)は、渡された id が db に実在するかを
ここで確かめてから書き込む。`name` `kind` は必須。スキーマに無い欄が
混じっていたら(`DEM/db/schema.py` の `Location` の列と照らして)そこで止める。

`area`(広さ)を持たせるときは、親との整合も確かめる: **親の広さ未満**、
かつ**同じ親を持つ場所(兄弟)を足しても親の広さを超えない**
(`DEM/data_access_logic/query/world_createion_query.py`)。

`parent_id` があるときは、**`start`〜`end` が親の `start`〜`end` に収まって
いるか**も確かめる(親がまだ無い時刻・既に終わった時刻に子を生まない)。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.data_access_logic.query import world_createion_query
from DEM.db.schema import Location
from DEM.db.schema_pydantic import to_dict


class CommitPlace(CommitDraft):
    """場所を一件、db へ確定して、格納後の中身を辞書で返す。

    `place` は JSON 文字列でも辞書でもよい。`id` キーは無視する
    (採番は db に任せる)。
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
        self._check_area(session, data)
        self._check_span(session, data)

        record = Location(**data)
        session.add(record)
        session.commit()
        return to_dict(record)

    @staticmethod
    def _check_area(session, data: dict) -> None:
        area = data.get("area")
        parent_id = data.get("parent_id")
        if area is None or parent_id is None:
            return

        parent = session.get(Location, parent_id)
        if parent.area is None:
            return

        if not area < parent.area:
            raise ValueError(
                f"area={area} が親(id={parent_id})の広さ {parent.area} 未満でない")

        siblings_area = session.scalar(
            world_createion_query.siblings_area_sum_select(parent_id))
        if siblings_area + area > parent.area:
            raise ValueError(
                f"area={area} を足すと、親(id={parent_id})の広さ {parent.area} を"
                f"兄弟の合計 {siblings_area} が超える")

    @staticmethod
    def _check_span(session, data: dict) -> None:
        parent_id = data.get("parent_id")
        if parent_id is None:
            return
        parent = session.get(Location, parent_id)
        world_createion_query.check_within_parent_span(
            parent, data.get("start"), data.get("end"), "location")
