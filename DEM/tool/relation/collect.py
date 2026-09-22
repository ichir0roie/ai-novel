#!/usr/bin/env python3
"""db から、人物と人物同士の相関を素の辞書に集める。HTML の描画の材料。"""
from __future__ import annotations

from sqlalchemy import select

from DEM.db.schema import Character, CharacterRelation

__all__ = ["character_dict", "relation_dict", "collect_relations"]


def character_dict(character) -> dict:
    return {
        "id": character.id, "name": character.name, "kind": character.kind,
        "sex": character.sex,
        "start": str(character.start) if character.start else None,
        "end": str(character.end) if character.end else None,
        "path": (f"{character.directory_path}/{character.id}.md"
                 if character.directory_path else f"{character.id}.md"),
    }


def relation_dict(relation) -> dict:
    return {
        "id": relation.id,
        "character_id_1": relation.character_id_1,
        "character_id_2": relation.character_id_2,
        "relation": relation.relation,
        "text": relation.text or "",
    }


def collect_relations(session) -> dict:
    """`{"characters": [...], "relations": [...]}`。人物は相関の有無に関わらず全員入れる。"""
    characters = session.scalars(select(Character).order_by(Character.id)).all()
    relations = session.scalars(select(CharacterRelation).order_by(CharacterRelation.id)).all()
    return {
        "characters": [character_dict(c) for c in characters],
        "relations": [relation_dict(r) for r in relations],
    }
