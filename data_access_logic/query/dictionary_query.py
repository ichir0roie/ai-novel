#!/usr/bin/env python3
from __future__ import annotations

from sqlalchemy import ColumnElement, Select, and_, false, or_, select, true

from db.schema import Idea
from db.stamp import Stamp


def idea_in_scope(place_ids=None, time: Stamp | None = None) -> ColumnElement[bool]:
    """`place_ids` は現在地から最上位までの場所(`common_query.idea_scope_ids`)。"""
    conditions = []
    if place_ids is not None:
        conditions.append(Idea.location_id.in_(list(place_ids)))
    if time is not None:
        conditions += [or_(Idea.start.is_(None), Idea.start <= time),
                       or_(Idea.end.is_(None), Idea.end > time)]
    return and_(true(), *conditions)


def ideas_by_keyword_select(keyword: str) -> Select:
    return ideas_by_terms_select([keyword])


def ideas_by_terms_select(terms, place_ids=None, time: Stamp | None = None) -> Select:
    """名前か本文に `terms` のどれかを含むアイデア。"""
    terms = [term for term in terms if term]
    if not terms:
        return select(Idea).where(false())
    return (select(Idea)
            .where(or_(*(Idea.name.contains(term, autoescape=True) for term in terms),
                       *(Idea.text.contains(term, autoescape=True) for term in terms)),
                   idea_in_scope(place_ids, time))
            .order_by(Idea.id))


def auto_generated_ideas_select() -> Select:
    return select(Idea).where(Idea.auto_generated.is_(True)).order_by(Idea.id)


def ideas_by_parent_select(parent_ids, place_ids=None, time: Stamp | None = None) -> Select:
    return (select(Idea)
            .where(Idea.parent_idea_id.in_(list(parent_ids)), idea_in_scope(place_ids, time))
            .order_by(Idea.id))
