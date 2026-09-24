#!/usr/bin/env python3
from __future__ import annotations

from sqlalchemy import ColumnElement, Select, false, or_, select

from db.schema import IDEA_KIND_CANDIDATE, Idea


def idea_not_candidate() -> ColumnElement[bool]:
    return or_(Idea.kind.is_(None), Idea.kind != IDEA_KIND_CANDIDATE)


def idea_in_scope(place_ids) -> ColumnElement[bool]:
    place_ids = list(place_ids)
    return or_(Idea.restrict_place_id.in_(place_ids),
               Idea.restrict_planet_id.in_(place_ids),
               Idea.restrict_world_id.in_(place_ids))


def ideas_by_keyword_select(keyword: str) -> Select:
    return ideas_by_terms_select([keyword])


def ideas_by_terms_select(terms, place_ids=None, include_candidates: bool = False) -> Select:
    """名前か本文に `terms` のどれかを含むアイデア。"""
    terms = [term for term in terms if term]
    if not terms:
        return select(Idea).where(false())
    query = select(Idea).where(or_(
        *(Idea.name.contains(term, autoescape=True) for term in terms),
        *(Idea.text.contains(term, autoescape=True) for term in terms)))
    if place_ids is not None:
        query = query.where(idea_in_scope(place_ids))
    if not include_candidates:
        query = query.where(idea_not_candidate())
    return query.order_by(Idea.id)


def candidate_ideas_select() -> Select:
    return select(Idea).where(Idea.kind == IDEA_KIND_CANDIDATE).order_by(Idea.id)


def ideas_by_parent_select(parent_ids, place_ids=None) -> Select:
    query = select(Idea).where(Idea.parent_idea_id.in_(list(parent_ids)), idea_not_candidate())
    if place_ids is not None:
        query = query.where(idea_in_scope(place_ids))
    return query.order_by(Idea.id)
