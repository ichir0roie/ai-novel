#!/usr/bin/env python3
"""語(辞書)のための問い合わせ。`DEM/claude_interface/world/` から使う。"""
from __future__ import annotations

from sqlalchemy import Select, select

from DEM.db.schema import Term


def terms_by_keyword_select(keyword: str) -> Select:
    return (select(Term)
            .where(Term.text.contains(keyword))
            .order_by(Term.id))
