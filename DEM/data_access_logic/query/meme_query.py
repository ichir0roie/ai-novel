#!/usr/bin/env python3
"""ミーム(`Meme`)の元を引く。元のテーブル(語・人物)の `meme_seeded` で見る。"""
from __future__ import annotations

from sqlalchemy import Select, select


def unseeded_select(model) -> Select:
    """**ミームをまだ抜き出していない `model` のレコード**(`meme_seeded` が false)。id 順。"""
    return (select(model)
            .where(model.meme_seeded.is_(False))
            .order_by(model.id))
