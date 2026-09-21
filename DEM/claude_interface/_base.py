#!/usr/bin/env python3
"""`claude_interface/` 全体の基底。`randomizer/` `story/` `sync/` `world/` に共通する部分。"""
from __future__ import annotations

import json

from DEM.db.schema import get_session


class Entrypoint:
    """すべての入口の基底。サブクラスは `run()` を実装する。"""

    def run(self):
        raise NotImplementedError


class SessionEntrypoint(Entrypoint):
    def run(self):
        with get_session() as session:
            return self.execute(session)

    def execute(self, session):
        raise NotImplementedError


class UnknownRecordError(ValueError):
    pass


class UnknownFieldError(ValueError):
    pass


class CommitEntrypoint(SessionEntrypoint):
    """確定する系入口の共通処理。サブクラスは `model` を指し、`parse`/`check_columns`/`check_exists` を使う。"""

    model: type

    @staticmethod
    def parse(payload: str | dict) -> dict:
        return json.loads(payload) if isinstance(payload, str) else dict(payload)

    @staticmethod
    def check_exists(session, model, id_: int | None, label: str) -> None:
        if id_ is not None and session.get(model, id_) is None:
            raise UnknownRecordError(
                f"{label}={id_} という id の {model.__tablename__} が見つからない")

    def check_columns(self, data: dict, model: type | None = None) -> None:
        model = model or self.model
        columns = {column.key for column in model.__table__.columns} - {"id"}
        unknown = set(data) - columns
        if unknown:
            raise UnknownFieldError(
                f"{model.__name__} のスキーマに無い欄: {sorted(unknown)}")
