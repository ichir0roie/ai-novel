#!/usr/bin/env python3
"""ミームの抜き出し(`meme`)と要約(`event_summary` / `episode_summary`)をまとめて作り直す。

出来事(`Event`)・話(`Episode`)を確定したときに、その場でまとめて呼ぶためのもの
(作品(`Story`)には要約が無いので、ミームの棚卸しだけ行う)。
"""
from __future__ import annotations

from sqlalchemy import select

from ai.time_keeper import episode_summary, event_summary, meme
from ai.time_keeper._ai import AIClient
from db.schema import Episode, Event, Session


def refresh(session: Session, ai: AIClient, record: Event | Episode | None = None) -> dict:
    """ミームを棚卸しし、`record` が出来事・話ならその要約も作る。件数を辞書で返す。"""
    memes_added = meme.refresh(session, ai)
    summarized = False
    if isinstance(record, Event):
        summarized = event_summary.summarize(session, record, ai) is not None
    elif isinstance(record, Episode):
        summarized = episode_summary.summarize(session, record, ai) is not None
    return {"memes_added": memes_added, "summarized": summarized}


def refresh_all(session: Session, ai: AIClient) -> dict:
    """ミームを棚卸しし、まだ要約の無い(または本文が変わった)出来事・話をすべて作り直す。

    `refresh` は確定したその一件だけを見るのに対して、こちらは表全体の取りこぼしを拾う
    (md を直接編集して `import_db` した場合など、確定の入口を通らなかった分もここで拾える)。
    件数を辞書で返す。
    """
    memes_added = meme.refresh(session, ai)
    events_summarized = sum(
        1 for event in session.scalars(select(Event)).all()
        if event_summary.summarize(session, event, ai) is not None)
    episodes_summarized = sum(
        1 for episode in session.scalars(select(Episode)).all()
        if episode_summary.summarize(session, episode, ai) is not None)
    return {"memes_added": memes_added, "events_summarized": events_summarized,
            "episodes_summarized": episodes_summarized}
