#!/usr/bin/env python3
"""`interface/` 全体の基底。`randomizer/` `story/` `sync/` `world/` に共通する部分。"""
from __future__ import annotations

import json

from db.schema import get_env_session


class Entrypoint:
    """すべての入口の基底。サブクラスは `run()` を実装する。"""

    def run(self):
        raise NotImplementedError


class SessionEntrypoint(Entrypoint):
    def run(self):
        with get_env_session() as session:
            return self.execute(session)

    def execute(self, session):
        raise NotImplementedError


class UnknownRecordError(ValueError):
    pass


class UnknownFieldError(ValueError):
    pass


class CommitEntrypoint(SessionEntrypoint):
    """確定する系入口の共通処理。サブクラスは `model` を指し、`parse`/`check_columns`/`check_exists` を使う。

    `execute()` はまとめて一つのトランザクションとして `session.begin()` に包む。
    `execute()` の中で `session.commit()` は呼ばない(成功時は抜けるときに
    まとめて commit、例外時は rollback される)。
    """

    model: type

    def run(self):
        with get_env_session() as session:
            with session.begin():
                return self.execute(session)

    @staticmethod
    def parse(payload: str | dict) -> dict:
        return json.loads(payload) if isinstance(payload, str) else dict(payload)

    @staticmethod
    def check_exists(session, model, id_: int | None, label: str) -> None:
        if id_ is not None and session.get(model, id_) is None:
            raise UnknownRecordError(
                f"{label}={id_} という id の {model.__tablename__} が見つからない")

    @staticmethod
    def finalize(session, record):
        """新しく作った record を db へ流し、書き込まれた値で読み直す。

        `StampType` のような列は bind するとき(`process_bind_param`)にしか
        型変換が掛からない。`flush` しただけでは record の属性は渡した生の値
        (例: 文字列の `"1"`)のまま残るので、`to_dict` に渡す前に `refresh` で
        db に書いた値を読み直し、`process_result_value` を通した本来の型
        (`Stamp` 等)に揃える。
        """
        session.flush()
        session.refresh(record)

    def check_columns(self, data: dict, model: type | None = None) -> None:
        model = model or self.model
        columns = {column.key for column in model.__table__.columns} - {"id"}
        unknown = set(data) - columns
        if unknown:
            raise UnknownFieldError(
                f"{model.__name__} のスキーマに無い欄: {sorted(unknown)}")
