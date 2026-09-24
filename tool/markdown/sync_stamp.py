#!/usr/bin/env python3
from __future__ import annotations

import os

STAMP_NAME = ".markdown_sync"

__all__ = ["STAMP_NAME", "stamp_path", "mark_synced", "edited_since_sync"]


def stamp_path(root: str) -> str:
    # 印は `root` の外に置く。`export_db` が `root` をまるごと消すため
    return os.path.join(os.path.dirname(os.path.abspath(root)), STAMP_NAME)


def mark_synced(root: str) -> None:
    path = stamp_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{os.path.abspath(root)}\n")


def edited_since_sync(root: str) -> list[str]:
    """印が無ければ比べようがないので空で返す。"""
    path = stamp_path(root)
    if not os.path.exists(path):
        return []
    synced = os.stat(path).st_mtime_ns
    edited = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            md = os.path.join(dirpath, filename)
            if os.stat(md).st_mtime_ns > synced:
                edited.append(md)
    return sorted(edited)
