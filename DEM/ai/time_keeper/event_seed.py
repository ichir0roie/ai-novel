#!/usr/bin/env python3
"""出来事の種(`EventSeed`)。作品・話・人物の筋書きから、時代・場所・固有名詞を抜いた出来事のアイデアを抜き出して貯め、毎日のルーチンでランダムに引く。

元の本文が変わったら、その元の種だけを抜き出し直す。
"""
from __future__ import annotations

import json
import random
import re

from sqlalchemy import delete, select

from DEM.ai.time_keeper import constants
from DEM.ai.time_keeper._ai import AIClient
from DEM.db.schema import (
    Character, Episode, EventSeed, EventSeedSource, Session, Story, summary_source_hash,
)

_SYSTEM_PROMPT = """\
あなたは物語の編集者です。
作品の筋書き・話の骨組み・人物の筋書きをいくつか番号つきで渡すので、それぞれから、ほかの時代・ほかの場所・ほかの人物にも起こせる「出来事の種」を抜き出してください。
- 人名・地名・組織名・その作品だけの用語と、年代を抜く。人物は「古参の番兵」「商家の娘」のような立場で書く。
- 一つの種は一〜二文。誰が、何をきっかけに、何をして、どんな揺れや変化が起きるかを書く。
- 作者の前書き・使用環境・書き方の約束・構成表など、出来事にならない文からは抜き出さない。
- 一つの元から 0〜3 件。同じ元の中で似た種は一つにまとめる。
JSON で答えてください。キーは seeds(各要素は source(元の番号)と text(種)の二つ)だけ。"""

_PLOT_SECTION = re.compile(r"^#[ \t]*plot[ \t]*\n(.*?)(?=^#[ \t]|\Z)", re.M | re.S)


def _schema(count: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "seeds": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "integer", "minimum": 1, "maximum": count},
                        "text": {"type": "string"},
                    },
                    "required": ["source", "text"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["seeds"],
        "additionalProperties": False,
    }


def _plot_section(text: str | None) -> str:
    match = _PLOT_SECTION.search(text or "")
    return match.group(1).strip() if match else ""


def _sources(session: Session) -> dict[tuple[str, int], str]:
    """種を抜き出す元。(種類, id) -> 本文。話は種(`key`)を、無ければ本文を使う。"""
    sources: dict[tuple[str, int], str] = {}
    for story in session.scalars(select(Story)).all():
        sources[("story", story.id)] = (story.text or "").strip()
    for episode in session.scalars(select(Episode)).all():
        sources[("episode", episode.id)] = (episode.key or "").strip() or (episode.text or "").strip()
    for character in session.scalars(select(Character)).all():
        sources[("character", character.id)] = _plot_section(character.text)
    return {key: text for key, text in sources.items() if text}


def _batches(items: list[tuple[tuple[str, int], str]]) -> list[list[tuple[tuple[str, int], str]]]:
    """一度に渡す本文の字数が `constants.EVENT_SEED_BATCH_LETTERS` を超えないように分ける。"""
    batches: list[list] = []
    letters = 0
    for item in items:
        if batches and letters + len(item[1]) <= constants.EVENT_SEED_BATCH_LETTERS:
            batches[-1].append(item)
            letters += len(item[1])
        else:
            batches.append([item])
            letters = len(item[1])
    return batches


def _drop(session: Session, row: EventSeedSource) -> None:
    session.execute(delete(EventSeed).where(EventSeed.event_seed_source_id == row.id))
    session.delete(row)


def refresh(session: Session, ai: AIClient) -> int:
    """元の本文が変わった・まだ抜き出していない元から種を抜き出す。消えた元の種は消す。足した種の件数を返す。"""
    sources = _sources(session)
    rows = {(row.source, row.source_id): row
            for row in session.scalars(select(EventSeedSource)).all()}
    for key, row in rows.items():
        if key not in sources or row.source_hash != summary_source_hash(sources[key]):
            _drop(session, row)
    session.commit()
    stale = [(key, text) for key, text in sources.items()
             if key not in rows or rows[key].source_hash != summary_source_hash(text)]

    added = 0
    for batch in _batches(stale):
        numbered = "\n\n".join(
            f"## 元{number}({kind})\n{text}" for number, ((kind, _), text) in enumerate(batch, start=1))
        decided = ai.try_generate_json(
            f"{numbered}\n\nそれぞれの元から出来事の種を抜き出してください。",
            _schema(len(batch)), system=_SYSTEM_PROMPT, timeout=constants.EVENT_SEED_TIMEOUT)
        if "seeds" not in decided:
            print(f"[time_keepr/seed] 元{len(batch)}件から種を抜き出せなかった。次の回に抜き出し直す")
            continue
        source_rows = []
        for (kind, source_id), text in batch:
            row = EventSeedSource(source=kind, source_id=source_id, source_hash=summary_source_hash(text))
            session.add(row)
            source_rows.append(row)
        session.flush()
        for seed in decided["seeds"] or []:
            if not isinstance(seed, dict):
                continue
            text = (seed.get("text") or "").strip()
            try:
                number = int(seed.get("source"))
            except (TypeError, ValueError):
                continue
            if text and 1 <= number <= len(source_rows):
                session.add(EventSeed(event_seed_source_id=source_rows[number - 1].id, text=text))
                added += 1
        session.commit()
    if stale:
        print(f"[time_keepr/seed] 元{len(stale)}件を抜き出し直し、種を{added}件足した")
    return added


def draw(session: Session, rng: random.Random, count: int = constants.EVENT_SEED_DRAW_COUNT) -> list[str]:
    """貯めた種から `count` 件をランダムに引く。"""
    seeds = session.scalars(select(EventSeed.text).order_by(EventSeed.id)).all()
    return rng.sample(list(seeds), min(count, len(seeds)))
