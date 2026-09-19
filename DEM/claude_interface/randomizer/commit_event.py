#!/usr/bin/env python3
"""JSON で受け取った出来事を一件、db へ確定する、claude が呼ぶ入口。

`create_random_event` が返した JSON を claude が文脈に合わせて書き換えた
ものを受け取る想定。db に触れるのはこのモジュールだけ——
`create_random_event` 側は一切 db を見ない。

実在レコードを指す欄（`place_id` `character_ids` `object_ids`
`parent_event_id`）は、渡された id が db に実在するかをここで確かめてから
書き込む。`character_ids` `object_ids` は id のリスト（多対多。何人・
何個体でも渡せる。省けば空の一覧のまま）で、`event_character` `event_object`
（中間テーブル）へ一件ずつ書き込む。`name` と `time` は必須。
スキーマに無い欄が混じっていたら（`DEM/db/schema.py` の `Event` の列と
照らして）そこで止める。

CLI としても呼べる:
    python3 -m DEM.claude_interface.randomizer.commit_event < 出来事.json
標準入力に JSON を流し込むと、確定後の中身を JSON で標準出力へ返す。
"""
from __future__ import annotations

import json
import sys

from sqlalchemy.orm import Session

from DEM.db.schema import (
    Character, Event, EventCharacter, EventObject, Location, Object,
    get_session,
)


class UnknownRecordError(ValueError):
    """渡された id が db に存在しないときに投げる。"""


class UnknownFieldError(ValueError):
    """`Event` のスキーマに無い欄が渡されたときに投げる。"""


def _check_exists(session: Session, model, id_: int | None, label: str) -> None:
    if id_ is not None and session.get(model, id_) is None:
        raise UnknownRecordError(f"{label}={id_} という id の {model.__tablename__} が見つからない")


def _json_safe(value):
    if value is not None and not isinstance(value, (str, int, float, bool)):
        return str(value)
    return value


def commit_event(event: str | dict) -> dict:
    """出来事を一件、db へ確定して、格納後の中身を辞書で返す。

    `event` は JSON 文字列でも辞書でもよい。`id` キーは無視する
    （採番は db に任せる）。
    """
    data = json.loads(event) if isinstance(event, str) else dict(event)
    data.pop("id", None)
    character_ids = [int(id_) for id_ in data.pop("character_ids", None) or []]
    object_ids = [int(id_) for id_ in data.pop("object_ids", None) or []]

    columns = {column.key for column in Event.__table__.columns} - {"id"}
    unknown = set(data) - columns
    if unknown:
        raise UnknownFieldError(f"Event のスキーマに無い欄: {sorted(unknown)}")
    if not data.get("name"):
        raise ValueError("name は必須")
    if data.get("time") is None:
        raise ValueError("time は必須")

    with get_session() as session:
        _check_exists(session, Event, data.get("parent_event_id"), "parent_event_id")
        _check_exists(session, Location, data.get("place_id"), "place_id")
        for character_id in character_ids:
            _check_exists(session, Character, character_id, "character_ids")
        for object_id in object_ids:
            _check_exists(session, Object, object_id, "object_ids")

        record = Event(**data)
        record.event_characters = [
            EventCharacter(character_id=character_id) for character_id in character_ids]
        record.event_objects = [
            EventObject(object_id=object_id) for object_id in object_ids]
        session.add(record)
        session.commit()
        return {
            **{column.key: _json_safe(getattr(record, column.key))
               for column in Event.__table__.columns},
            "character_ids": character_ids,
            "object_ids": object_ids,
        }


if __name__ == "__main__":
    result = commit_event(sys.stdin.read())
    print(json.dumps(result, ensure_ascii=False, indent=2))
