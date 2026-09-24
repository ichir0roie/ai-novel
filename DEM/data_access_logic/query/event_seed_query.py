#!/usr/bin/env python3
"""出来事の種(`EventSeed`)の元を引く。元のテーブル(作品・話・人物・出来事)の `event_seeded` で見る。"""
from __future__ import annotations

from sqlalchemy import Select, select


def unseeded_select(model) -> Select:
    """**種をまだ抜き出していない `model` のレコード**(`event_seeded` が false)。id 順。"""
    return (select(model)
            .where(model.event_seeded.is_(False))
            .order_by(model.id))
