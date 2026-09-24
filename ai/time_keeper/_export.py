#!/usr/bin/env python3
"""常駐ループが一歩進めるたびに `worlds/` を書き出す。"""
from __future__ import annotations

from tool.markdown.export_db import WORLDS_ROOT, export_db


def export_step(when: str, root: str = WORLDS_ROOT) -> None:
    counts = export_db(root)
    print(f"[time_keepr/export] {when}: {counts}")
