#!/usr/bin/env python3
"""**`claude_interface/` 全体の基底。**

`randomizer/` `story/` `sync/` `world/` の四領域に共通する部分だけをここへ
置く。領域ごとの共通処理は `<領域>/_base.py` に置き、ここを継ぐ。

呼び出し側(claude)は、各ファイル先頭に定義された継承クラスをインスタンス化
して `run()` を呼ぶだけでよい(CLI 引数のパースはしない。`readme.md` の
「一つの呼び出し機能だけ」がそのままクラス一つに対応する)。
"""
from __future__ import annotations

import json

from DEM.db.schema import get_session


class Entrypoint:
    """すべての入口の基底。サブクラスは `run()` を実装する。"""

    def run(self):
        raise NotImplementedError


class SessionEntrypoint(Entrypoint):
    """db セッションを開いて `execute(session)` へ渡す。"""

    def run(self):
        with get_session() as session:
            return self.execute(session)

    def execute(self, session):
        raise NotImplementedError


class UnknownRecordError(ValueError):
    """渡された id が db に存在しないときに投げる。"""


class UnknownFieldError(ValueError):
    """対象のスキーマに無い欄が渡されたときに投げる。"""


class CommitEntrypoint(SessionEntrypoint):
    """**「確定する」系入口の共通処理。**

    サブクラスは `model`(対象の ORM モデル)をクラス属性で指し、
    `execute(session)` の中で `parse` `check_columns` `check_exists` を使う。
    """

    model: type

    @staticmethod
    def parse(payload: str | dict) -> dict:
        """JSON 文字列でも辞書でも受け取れるようにする。"""
        return json.loads(payload) if isinstance(payload, str) else dict(payload)

    @staticmethod
    def check_exists(session, model, id_: int | None, label: str) -> None:
        """実在レコードを指す欄が、渡された時点で db にあるか確かめる。"""
        if id_ is not None and session.get(model, id_) is None:
            raise UnknownRecordError(
                f"{label}={id_} という id の {model.__tablename__} が見つからない")

    def check_columns(self, data: dict) -> None:
        """`model` のスキーマに無い欄が混ざっていないか確かめる。"""
        columns = {column.key for column in self.model.__table__.columns} - {"id"}
        unknown = set(data) - columns
        if unknown:
            raise UnknownFieldError(
                f"{self.model.__name__} のスキーマに無い欄: {sorted(unknown)}")
