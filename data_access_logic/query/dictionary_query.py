#!/usr/bin/env python3
from __future__ import annotations

from sqlalchemy import Select, select

from db.schema import Idea


def ideas_by_keyword_select(keyword: str) -> Select:
    return (select(Idea)
            .where(Idea.text.contains(keyword))
            .order_by(Idea.id))
