#!/usr/bin/env python3
"""人物相関の HTML を `worlds/character_relation/relation.html` へ書き出す。`export_db` から呼ばれる。"""
from __future__ import annotations

import os

from DEM.tool.relation.collect import collect_relations
from DEM.tool.relation.render_html import render_html

__all__ = ["render_relations"]


def render_relations(session, root: str) -> str:
    """書き出したファイルのパスを返す。"""
    path = os.path.join(root, "character_relation", "relation.html")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_html(collect_relations(session)))
    return path
