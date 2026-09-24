#!/usr/bin/env python3
"""出来事の種(`EventSeed`)。作品・話・人物の筋書き・出来事から、時代・場所・固有名詞を抜いた出来事のアイデアを抜き出して貯め、毎日のルーチンでランダムに引く。

抜き出しは元のレコードごとに一度だけ(`event_seeded` を立てる)。抜き出し直すには、元の `event_seeded` を false に戻す。
"""
from __future__ import annotations

import random
import re

from sqlalchemy import select

from DEM.ai.time_keeper import constants
from DEM.ai.time_keeper._ai import AIClient
from DEM.data_access_logic.query import event_seed_query
from DEM.db.schema import Character, Episode, Event, EventSeed, Session, Story

_SYSTEM_PROMPT = """\
あなたは物語の編集者です。
作品の筋書き・話の骨組み・人物の筋書き・起きた出来事をいくつか番号つきで渡すので、それぞれから、ほかの時代・ほかの場所・ほかの人物にも起こせる「出来事の種」を抜き出してください。
- 人名・地名・組織名・その作品だけの用語と、年代を抜く。人物は「古参の番兵」「商家の娘」のような立場で書く。
- 一つの種は一〜二文。誰が、何をきっかけに、何をして、どんな揺れや変化が起きるかを書く。
- 作者の前書き・使用環境・書き方の約束・構成表など、出来事にならない文からは抜き出さない。
- 一つの元から 0〜3 件。同じ元の中で似た種は一つにまとめる。
JSON で答えてください。キーは seeds(種の文字列のリスト)だけ。"""

_PLOT_SECTION = re.compile(r"^#[ \t]*plot[ \t]*\n(.*?)(?=^#[ \t]|\Z)", re.M | re.S)


_SCHEMA = {
    "type": "object",
    "properties": {"seeds": {"type": "array", "items": {"type": "string"}}},
    "required": ["seeds"],
    "additionalProperties": False,
}


def _plot_section(text: str | None) -> str:
    match = _PLOT_SECTION.search(text or "")
    return match.group(1).strip() if match else ""


# 元のテーブルと、そこから種を抜き出す本文。話は種(`key`)を、無ければ本文を使う。
_SOURCE_TEXTS = (
    (Story, lambda story: story.text),
    (Episode, lambda episode: (episode.key or "").strip() or episode.text),
    (Character, lambda character: _plot_section(character.text)),
    (Event, lambda event: event.text),
)

_Pending = tuple[Story | Episode | Character | Event, str]


def _batches(items: list[_Pending]) -> list[list[_Pending]]:
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


def _pending(session: Session) -> list[_Pending]:
    """まだ抜き出していない元。本文が空の元は、書かれるまで待つ(印を立てない)。"""
    pending = []
    for model, text_of in _SOURCE_TEXTS:
        for record in session.scalars(event_seed_query.unseeded_select(model)).all():
            text = (text_of(record) or "").strip()
            if text:
                pending.append((record, text))
    return pending


def refresh(session: Session, ai: AIClient) -> int:
    """まだ抜き出していない元から種を抜き出し、元に `event_seeded` を立てる。足した種の件数を返す。"""
    pending = _pending(session)
    added = 0
    for batch in _batches(pending):
        numbered = "\n\n".join(
            f"## 元{number}({record.__tablename__})\n{text}"
            for number, (record, text) in enumerate(batch, start=1))
        decided = ai.try_generate_json(
            f"{numbered}\n\nそれぞれの元から出来事の種を抜き出してください。",
            _SCHEMA, system=_SYSTEM_PROMPT, timeout=constants.EVENT_SEED_TIMEOUT)
        if "seeds" not in decided:
            print(f"[time_keepr/seed] 元{len(batch)}件から種を抜き出せなかった。次の回に抜き出し直す")
            continue
        for seed in decided["seeds"] or []:
            text = seed.strip() if isinstance(seed, str) else ""
            if text:
                session.add(EventSeed(text=text))
                added += 1
        for record, _ in batch:
            record.event_seeded = True
        session.commit()
    if pending:
        print(f"[time_keepr/seed] 元{len(pending)}件から抜き出し、種を{added}件足した")
    return added


def draw(session: Session, rng: random.Random, count: int = constants.EVENT_SEED_DRAW_COUNT) -> list[str]:
    """貯めた種から `count` 件をランダムに引く。"""
    seeds = session.scalars(select(EventSeed.text).order_by(EventSeed.id)).all()
    return rng.sample(list(seeds), min(count, len(seeds)))
