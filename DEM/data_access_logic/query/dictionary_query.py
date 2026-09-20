#!/usr/bin/env python3
"""**語(辞書)のための問い合わせ。** 下地の実装。

claude はここを直接呼ばない。`DEM/claude_interface/world/` の入口越しに使う。

`common_query.py` と同じく、関数は `Select` を返すだけにとどめる
(実行と ORM→dict の変換は呼び出し側へ渡す)。
"""
from __future__ import annotations

from sqlalchemy import Select, select

from DEM.db.schema import Term


def terms_by_keyword_select(keyword: str) -> Select:
    """**語の本文(`text`)にそのキーワードを含むもの**を探す。"""
    return (select(Term)
            .where(Term.text.contains(keyword))
            .order_by(Term.id))
