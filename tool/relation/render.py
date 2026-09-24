#!/usr/bin/env python3
from __future__ import annotations

import os

from tool.relation.collect import collect_relations
from tool.relation.render_html import render_html

__all__ = ["render_relations"]


def render_relations(session, root: str) -> str:
    path = os.path.join(root, "maps", "relation.html")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_html(collect_relations(session)))
    return path
