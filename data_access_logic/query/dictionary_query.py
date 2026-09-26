#!/usr/bin/env python3
from __future__ import annotations

from sqlalchemy import ColumnElement, Select, and_, false, or_, select, true

from db.schema import Idea
from db.stamp import Stamp


def idea_in_scope(place_ids=None, time: Stamp | None = None) -> ColumnElement[bool]:
    """`place_ids` は現在地から最上位までの場所(`common_query.idea_scope_ids`)。"""
    conditions = []
    if place_ids is not None:
        conditions.append(or_(Idea.location_id.in_(list(place_ids)),
                              and_(Idea.alias_of_idea_id.is_not(None), Idea.location_id.is_(None))))
    if time is not None:
        conditions += [or_(Idea.start.is_(None), Idea.start <= time),
                       or_(Idea.end.is_(None), Idea.end > time)]
    return and_(true(), *conditions)


def alias_in_scope(place_ids=None, time: Stamp | None = None) -> ColumnElement[bool]:
    """呼び名は、場所・時代の列が空ならどこでも・いつでも使う。
    `place_ids` / `time` を渡さなければ、その列が空の呼び名だけに当たる。
    """
    location = Idea.location_id.is_(None)
    if place_ids is not None:
        location = or_(location, Idea.location_id.in_(list(place_ids)))
    if time is None:
        period = and_(Idea.start.is_(None), Idea.end.is_(None))
    else:
        period = and_(or_(Idea.start.is_(None), Idea.start <= time),
                      or_(Idea.end.is_(None), Idea.end > time))
    return and_(location, period)


def aliases_select(essence_ids, place_ids=None, time: Stamp | None = None) -> Select:
    return (select(Idea)
            .where(Idea.alias_of_idea_id.in_(list(essence_ids)), alias_in_scope(place_ids, time))
            .order_by(Idea.start.desc().nulls_last(), Idea.id))


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


def later_ideas_select(place_ids, time: Stamp) -> Select:
    """`time` より後に始まる、`place_ids` の場所で効くアイデア(呼び名は除く)。"""
    return (select(Idea)
            .where(Idea.location_id.in_(list(place_ids)), Idea.alias_of_idea_id.is_(None),
                   Idea.start > time)
            .order_by(Idea.start, Idea.id))
