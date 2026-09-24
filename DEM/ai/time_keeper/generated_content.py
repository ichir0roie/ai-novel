#!/usr/bin/env python3
"""ミームの抜き出し(`meme`)と要約(`event_summary` / `episode_summary`)をまとめて作り直す。

出来事(`Event`)・話(`Episode`)を確定したときに、その場でまとめて呼ぶためのもの
(作品(`Story`)には要約が無いので、ミームの棚卸しだけ行う)。
"""
from __future__ import annotations

from DEM.ai.time_keeper import episode_summary, event_summary, meme
from DEM.ai.time_keeper._ai import AIClient
from DEM.db.schema import Episode, Event, Session


def refresh(session: Session, ai: AIClient, record: Event | Episode | None = None) -> dict:
    """ミームを棚卸しし、`record` が出来事・話ならその要約も作る。件数を辞書で返す。"""
    memes_added = meme.refresh(session, ai)
    summarized = False
    if isinstance(record, Event):
        summarized = event_summary.summarize(session, record, ai) is not None
    elif isinstance(record, Episode):
        summarized = episode_summary.summarize(session, record, ai) is not None
    return {"memes_added": memes_added, "summarized": summarized}
