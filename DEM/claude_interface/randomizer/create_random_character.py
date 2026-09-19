#!/usr/bin/env python3
"""ランダムな人物の下書きを一件作る、claude が呼ぶ入口。

`DEM.randomizer.random_character_generator.build_character` の薄いラッパー。
実在レコードを指す欄（`kind_id` `root_place_name` `born_place_id` `belong_id`）は
呼び出し側が実在の id を渡す。このモジュールは、渡された id が db に実在するかを
確かめてから build する。

`build()`（flush まで）で止め、`create()`（commit）はしない。返す `Character` は
flush 済み・未 commit のまま同じ session に載っている。呼び出し側が中身を見て
（固有名詞や text はまだ仮の値のままなので）直してから、
`commit_character()` で確定するか `discard_character()` で捨てる。
"""
from __future__ import annotations

from sqlalchemy.orm import Session, object_session

from DEM.db.schema import Character, Kind, Location, Object, get_session
from DEM.randomizer.random_character_generator import build_character


class UnknownRecordError(ValueError):
    """渡された id が db に存在しないときに投げる。"""


def _check_exists(session: Session, model, id_: int | None, label: str) -> None:
    if id_ is not None and session.get(model, id_) is None:
        raise UnknownRecordError(f"{label}={id_} という id の {model.__tablename__} が見つからない")


def create_random_character(
    *,
    kind_id: int,
    root_place_name: int | None = None,
    born_place_id: int | None = None,
    belong_id: int | None = None,
    **overrides,
) -> Character:
    """ランダムな人物の下書きを一件、flush まで進めて返す。

    `kind_id`（種別）は必須。`root_place_name`（起点の場所）・`born_place_id`
    （出身地）・`belong_id`（所属個体）は分かっていれば渡す。どれも db に実在する
    id でなければ `UnknownRecordError`。性別・体格・口調・性格などその他の欄は
    `overrides` で上書きできる（`build_character` にそのまま渡る）。
    """
    with get_session() as check:
        _check_exists(check, Kind, kind_id, "kind_id")
        _check_exists(check, Location, root_place_name, "root_place_name")
        _check_exists(check, Location, born_place_id, "born_place_id")
        _check_exists(check, Object, belong_id, "belong_id")

    return build_character(
        kind_id=kind_id,
        root_place_name=root_place_name,
        born_place_id=born_place_id,
        belong_id=belong_id,
        **overrides,
    )


def commit_character(character: Character) -> Character:
    """レビューを終えた下書きを確定する（`character` が載っている session を commit）。"""
    session = object_session(character)
    if session is None:
        raise ValueError("この Character はどの session にも載っていない")
    session.commit()
    return character


def discard_character(character: Character) -> None:
    """下書きを捨てる（`character` が載っている session を rollback）。"""
    session = object_session(character)
    if session is None:
        raise ValueError("この Character はどの session にも載っていない")
    session.rollback()
