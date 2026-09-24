#!/usr/bin/env python3
"""アイデア(`Idea`)・ミーム(`Meme`)の中身を、Claude Code にネット検索させて検め、妥当性と補足を `review` 欄へ書く。

`local_ai`(Ollama)はネットを引けないので、ここだけは claude_ai 固有。
`review` が空のものを「まだ検めていない」とみなす。検め直すときは id を名指しする。
"""
from __future__ import annotations

from sqlalchemy import or_, select

from ai.claude_code import ai_client
from db.schema import Idea, Meme, Session

REVIEW_TOOLS = ("WebSearch", "WebFetch")
# 検索を何度も挟むので、道具なしの呼び出しより長く待つ。
REVIEW_TIMEOUT = 900.0
# 一度の呼び出しで検めさせる本文の字数の上限。一件でこれを超えるものは一件だけで渡す。
REVIEW_BATCH_LETTERS = 3000

_SYSTEM_PROMPT = """\
あなたは創作の設定を検める、科学・歴史・思想に詳しい校閲者です。
小説の世界の設定(アイデア)か、人物の行動原理の芯になる考え方(ミーム)を番号つきで渡すので、\
それぞれをネット検索で調べ、内容の妥当性を検め、書き手の役に立つ補足を書いてください。
- 架空の世界の設定なので、架空であること自体は誤りとしない。現実の科学・技術・歴史・社会・思想に照らして、\
  ありえる点・無理のある点、設定の中での食い違いを挙げる。
- 補足には、現実で近いもの(実在の現象・技術・制度・歴史上の出来事・思想や心理学の知見)と、\
  設定を厚くするのに使える事実を書く。
- ミームは、現実にその考え方を持った人・集団・思想の系譜や、心理学・社会学での裏付けを挙げる。
- 検索で確かめた事実だけを書き、分からないことは分からないと書く。
- 各 review は次の三つの小見出しを持つ markdown にする。見出しは必ず `##` を使い、`#` 一つの見出しは使わない。
  ## 妥当性
  ## 補足
  ## 出典
  出典は `- [題](URL)` の箇条書きにする。
- 全体で 400〜800 字を目安にする。
JSON で答えてください。キーは reviews だけ。各要素は number(番号)と review(検めた結果の markdown)の二つ。"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer"},
                    "review": {"type": "string"},
                },
                "required": ["number", "review"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reviews"],
    "additionalProperties": False,
}

MODELS = {"idea": Idea, "meme": Meme}


def _describe(record: Idea | Meme) -> str:
    if isinstance(record, Idea):
        return f"アイデア「{record.name}」(種類: {record.kind})\n{record.text}"
    return f"ミーム(分類: {record.category or '未分類'})\n{record.text}"


def _batches(records: list[Idea | Meme]) -> list[list[Idea | Meme]]:
    batches: list[list] = []
    letters = 0
    for record in records:
        size = len(_describe(record))
        if batches and letters + size <= REVIEW_BATCH_LETTERS:
            batches[-1].append(record)
            letters += size
        else:
            batches.append([record])
            letters = size
    return batches


def targets(session: Session, table: str, ids: list[int] | None = None, limit: int | None = None) -> list:
    """検める対象。`ids` を渡せばそれ(検め済みでも検め直す)、無ければ `review` が空で本文のあるもの。"""
    model = MODELS[table]
    query = select(model).order_by(model.id)
    if ids is not None:
        query = query.where(model.id.in_(ids))
    else:
        query = query.where(or_(model.review.is_(None), model.review == ""), model.text != "")
    if limit is not None:
        query = query.limit(limit)
    return list(session.scalars(query).all())


def review(session: Session, table: str, ids: list[int] | None = None, limit: int | None = None) -> int:
    """`table`("idea" / "meme")の対象を検め、`review` を書いて commit する。書いた件数を返す。

    AI が答えなかったものは空のまま残し、次の回に検め直す。
    """
    records = targets(session, table, ids, limit)
    written = 0
    for batch in _batches(records):
        numbered = "\n\n".join(
            f"## {number}\n{_describe(record)}" for number, record in enumerate(batch, start=1))
        decided = ai_client.try_generate_json(
            f"{numbered}\n\nそれぞれをネット検索で検め、妥当性と補足を書いてください。",
            _SCHEMA, system=_SYSTEM_PROMPT, timeout=REVIEW_TIMEOUT, tools=REVIEW_TOOLS)
        for item in decided.get("reviews") or []:
            if not isinstance(item, dict) or not isinstance(item.get("review"), str):
                continue
            try:
                number = int(item.get("number"))
            except (TypeError, ValueError):
                continue
            text = item["review"].strip()
            if 1 <= number <= len(batch) and text:
                batch[number - 1].review = text
                written += 1
        session.commit()
    if records:
        print(f"[claude_code/reviewer] {table} {len(records)}件のうち、{written}件を検めた")
    return written
