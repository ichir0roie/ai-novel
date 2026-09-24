#!/usr/bin/env python3
from __future__ import annotations

from sqlalchemy import Select, select

from data_access_logic.query import dictionary_query
from db.schema import Idea


def unseeded_select(model) -> Select:
    query = select(model).where(model.meme_seeded.is_(False))
    if model is Idea:
        query = query.where(dictionary_query.idea_not_candidate())
    return query.order_by(model.id)
