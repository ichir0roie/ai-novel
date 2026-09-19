#!/usr/bin/env python3
"""JSON で受け取った人物を一件、db へ確定する、claude が呼ぶ入口。

`create_random_character` が返した JSON を claude が文脈に合わせて書き換えた
ものを受け取る想定。db に触れるのはこのモジュールだけ——
`create_random_character` 側は一切 db を見ない。

実在レコードを指す欄（`kind_id` `root_place_name` `born_place_id`
`belong_id`）は、渡された id が db に実在するかをここで確かめてから書き込む。
`kind_id` は必須（種別なしの人物は作らない）。スキーマに無い欄が混じっていたら
（`DEM/db/schema.py` の `Character` の列と照らして）そこで止める。

CLI としても呼べる:
    python3 -m DEM.claude_interface.randomizer.commit_character < 人物.json
標準入力に JSON を流し込むと、確定後の中身を JSON で標準出力へ返す。
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal

from sqlalchemy.orm import Session

from DEM.db.schema import Character, Kind, Location, Object, get_session


class UnknownRecordError(ValueError):
    """渡された id が db に存在しないときに投げる。"""


class UnknownFieldError(ValueError):
    """`Character` のスキーマに無い欄が渡されたときに投げる。"""


def _check_exists(session: Session, model, id_: int | None, label: str) -> None:
    if id_ is not None and session.get(model, id_) is None:
        raise UnknownRecordError(f"{label}={id_} という id の {model.__tablename__} が見つからない")


def _json_safe(value):
    """`Decimal`（`height` 等）と `Stamp`（`start`/`end`）を JSON にできる形へ寄せる。"""
    if isinstance(value, Decimal):
        return float(value)
    if value is not None and not isinstance(value, (str, int, float, bool)):
        return str(value)
    return value


def commit_character(character: str | dict) -> dict:
    """人物を一件、db へ確定して、格納後の中身を辞書で返す。

    `character` は JSON 文字列でも辞書でもよい。`id` キーは無視する
    （採番は db に任せる）。
    """
    data = json.loads(character) if isinstance(character, str) else dict(character)
    data.pop("id", None)

    columns = {column.key for column in Character.__table__.columns} - {"id"}
    unknown = set(data) - columns
    if unknown:
        raise UnknownFieldError(f"Character のスキーマに無い欄: {sorted(unknown)}")
    if data.get("kind_id") is None:
        raise ValueError("kind_id は必須")

    with get_session() as session:
        _check_exists(session, Kind, data.get("kind_id"), "kind_id")
        _check_exists(session, Location, data.get("root_place_name"), "root_place_name")
        _check_exists(session, Location, data.get("born_place_id"), "born_place_id")
        _check_exists(session, Object, data.get("belong_id"), "belong_id")

        record = Character(**data)
        session.add(record)
        session.commit()
        return {
            column.key: _json_safe(getattr(record, column.key))
            for column in Character.__table__.columns
        }


if __name__ == "__main__":
    result = commit_character(sys.stdin.read())
    print(json.dumps(result, ensure_ascii=False, indent=2))
