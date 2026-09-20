#!/usr/bin/env python3
"""JSON で受け取った内容で、**既にある**場所を一件、db 上で直す、claude が呼ぶ入口。

新しく場所を作るのは `commit_place.CommitPlace` の仕事。ここは、既に確定
済みの場所の欄(広さ・環境など)を後から直すためだけの入口——`id` で対象を
指定し、渡した欄だけを上書きする(渡さなかった欄はそのまま)。

`id` の実在確認と、スキーマに無い欄の混入チェックは他の「確定する」入口と
同じ。`area` を直すときは `CommitPlace` と同じ制約(親未満、かつ兄弟(自分を
除く)の合計を足しても親の広さを超えない)を、直した後の値で確かめる。
"""
from __future__ import annotations

from sqlalchemy import func, select

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Location
from DEM.db.schema_pydantic import to_dict


class UpdatePlace(CommitDraft):
    """場所を一件、渡した欄だけ書き換えて db へ確定し、格納後の中身を返す。

    `place` は JSON 文字列でも辞書でもよい。`id` は直す対象を指すので必須
    (`commit_place.CommitPlace` と違い、ここでは無視しない)。
    """

    model = Location

    def __init__(self, place: str | dict):
        self.place = place

    def execute(self, session) -> dict:
        data = self.parse(self.place)
        place_id = data.pop("id", None)
        if place_id is None:
            raise ValueError("id は必須(直す対象の場所)")
        self.check_columns(data)

        record = session.get(Location, place_id)
        if record is None:
            raise ValueError(f"id={place_id} という場所が見つからない")

        if "area" in data:
            self._check_area(session, record, data["area"])

        for key, value in data.items():
            setattr(record, key, value)
        session.commit()
        return to_dict(record)

    @staticmethod
    def _check_area(session, record: Location, area) -> None:
        if area is None or record.parent_id is None:
            return
        parent = session.get(Location, record.parent_id)
        if parent is None or parent.area is None:
            return
        if not area < parent.area:
            raise ValueError(
                f"area={area} が親(id={record.parent_id})の広さ {parent.area} 未満でない")

        siblings_area = session.scalar(
            select(func.coalesce(func.sum(Location.area), 0))
            .where(Location.parent_id == record.parent_id)
            .where(Location.id != record.id))
        if siblings_area + area > parent.area:
            raise ValueError(
                f"area={area} を足すと、親(id={record.parent_id})の広さ "
                f"{parent.area} を兄弟(自分を除く)の合計 {siblings_area} が超える")
