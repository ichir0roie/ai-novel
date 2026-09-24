#!/usr/bin/env python3
"""ミーム(`Meme`)。アイデア(`Idea`)・oracle(著者の覚え書き)・人物の筋書きから、
人物の行動原理の芯になりうる考え方を抜き出して貯める。

抜き出しは元のレコードごとに一度だけで、`meme_seeded` で管理する。false に戻すと、次の抽出で抜き出し直す。
ミームどうし・元との関係は持たない(移り変わり・伝染していくため)。
"""
from __future__ import annotations

import re

from ai.time_keeper import constants
from ai.time_keeper._ai import AIClient
from data_access_logic.query import meme_query
from db.schema import Character, Idea, Meme, Oracle, Session

_SYSTEM_PROMPT = """\
あなたは物語の編集者です。
用語の説明・著者の創作についての覚え書き・人物の筋書きをいくつか番号つきで渡すので、それぞれから、\
人物の行動原理の芯になりうる「ミーム」(繰り返し現れる考え方・価値観・行動の型)を抜き出してください。
- 人名・地名・組織名・その作品だけの固有名詞を抜き、他の人物にも乗り移りうる普遍的な考え方として書く。
- 一つのミームは一文。何を大事にし、何を避け、何をきっかけに動くかが分かるように書く。
- 作者の前書き・使用環境・書き方の約束など、考え方にならない文からは抜き出さない。
- 一つの元から 0〜3 件。同じ元の中で似たミームは一つにまとめる。
JSON で答えてください。キーは memes(ミームの文字列のリスト)だけ。"""

_SCHEMA = {
    "type": "object",
    "properties": {"memes": {"type": "array", "items": {"type": "string"}}},
    "required": ["memes"],
    "additionalProperties": False,
}

_PLOT_SECTION = re.compile(r"^#[ \t]*plot[ \t]*\n(.*?)(?=^#[ \t]|\Z)", re.M | re.S)


def _plot_section(text: str | None) -> str:
    match = _PLOT_SECTION.search(text or "")
    return match.group(1).strip() if match else ""


# 元のテーブルと、そこから抜き出す本文。人物は `# plot` の節だけを使う。
_SOURCE_TEXTS = (
    (Idea, lambda idea: idea.text),
    (Oracle, lambda oracle: oracle.text),
    (Character, lambda character: _plot_section(character.text)),
)

_Pending = tuple[Idea | Oracle | Character, str]


def _batches(items: list[_Pending], limit: int) -> list[list[_Pending]]:
    """一度に渡す本文(各要素の二つ目)の字数が `limit` を超えないように分ける。"""
    batches: list[list[_Pending]] = []
    letters = 0
    for item in items:
        if batches and letters + len(item[1]) <= limit:
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
        for record in session.scalars(meme_query.unseeded_select(model)).all():
            text = (text_of(record) or "").strip()
            if text:
                pending.append((record, text))
    return pending


def refresh(session: Session, ai: AIClient) -> int:
    """まだ抜き出していない元からミームを抜き出し、元に `meme_seeded` を立てる。足したミームの件数を返す。"""
    pending = _pending(session)
    added = 0
    for batch in _batches(pending, constants.MEME_BATCH_LETTERS):
        numbered = "\n\n".join(
            f"## 元{number}({record.__tablename__})\n{text}"
            for number, (record, text) in enumerate(batch, start=1))
        decided = ai.try_generate_json(
            f"{numbered}\n\nそれぞれの元からミームを抜き出してください。",
            _SCHEMA, system=_SYSTEM_PROMPT, timeout=constants.MEME_TIMEOUT)
        if "memes" not in decided:
            print(f"[time_keepr/meme] 元{len(batch)}件からミームを抜き出せなかった。次の回に抜き出し直す")
            continue
        for meme in decided["memes"] or []:
            text = meme.strip() if isinstance(meme, str) else ""
            if text:
                session.add(Meme(text=text))
                added += 1
        for record, _ in batch:
            record.meme_seeded = True
        session.commit()
    if pending:
        print(f"[time_keepr/meme] 元{len(pending)}件から抜き出し、ミームを{added}件足した")
    return added
