#!/usr/bin/env python3
"""出来事の本文の要約(`EventSummary`)。次の出来事へ直前の出来事を渡すとき、本文の代わりに使う。"""
from __future__ import annotations

import json

from sqlalchemy import select

from ai.time_keeper import constants
from ai.time_keeper._ai import AIClient
from db.schema import Event, EventSummary, Session, summary_source_hash

_SYSTEM_PROMPT = """\
あなたは日本語の小説の編集者です。
ある出来事の本文を渡すので、次の出来事を考える人へ渡す要約を作ってください。
誰が、誰に対して、何をして、どうなったかを起きた順に書き、終わっていないこと(残った問題・約束・謎)があれば最後に書いてください。
本文の文や言い回しを写さず、セリフも引かないでください。場面の分け方・締め方・文体には触れないでください。
三〜五文にまとめてください。
JSON で答えてください。キーは text(要約)だけ。"""

_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}


def summarize(session: Session, event: Event, ai: AIClient) -> str | None:
    """`event` の本文の要約。本文が前に要約したときのままなら作り直さない。作れなければ None。"""
    text = (event.text or "").strip()
    if not text:
        return None
    digest = summary_source_hash(text)
    row = session.scalars(select(EventSummary).where(EventSummary.event_id == event.id)).first()
    if row is not None and row.source_hash == digest:
        return row.text

    source = {"name": event.name, "start": str(event.start) if event.start else None,
              "end": str(event.end) if event.end else None, "text": text}
    decided = ai.try_generate_json(
        f"出来事: {json.dumps(source, ensure_ascii=False)}\nこの出来事を要約してください。",
        _SCHEMA, system=_SYSTEM_PROMPT, timeout=constants.EVENT_SUMMARY_TIMEOUT)
    summary = (decided.get("text") or "").strip()
    if not summary:
        return None
    if row is None:
        row = EventSummary(event_id=event.id)
        session.add(row)
    row.source_hash = digest
    row.text = summary
    session.commit()
    return summary
