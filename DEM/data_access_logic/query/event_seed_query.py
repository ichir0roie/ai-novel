#!/usr/bin/env python3
"""出来事の種(`EventSeed`)の元を引く。元のテーブル(作品・話・人物・出来事)ごとに、`EventSeedSource` の id 列で結ぶ。"""
from __future__ import annotations

from sqlalchemy import Select, exists, select

from DEM.db.schema import Character, Episode, Event, EventSeedSource, Story

SOURCE_COLUMNS = {
    Story: EventSeedSource.story_id,
    Episode: EventSeedSource.episode_id,
    Character: EventSeedSource.character_id,
    Event: EventSeedSource.event_id,
}


def unseeded_select(model) -> Select:
    """**種をまだ抜き出していない `model` のレコード**(`EventSeedSource` に行が無いもの)。id 順。"""
    column = SOURCE_COLUMNS[model]
    return (select(model)
            .where(~exists().where(column == model.id))
            .order_by(model.id))


def seeded_select(model) -> Select:
    """**抜き出し済みの元の行と、その元のレコード。** 元が消えていればレコードは None。"""
    column = SOURCE_COLUMNS[model]
    return (select(EventSeedSource, model)
            .outerjoin(model, column == model.id)
            .where(column.is_not(None))
            .order_by(EventSeedSource.id))
