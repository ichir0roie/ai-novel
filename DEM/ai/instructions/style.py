#!/usr/bin/env python3
"""文体の特徴を、プロンプトへ埋め込める定数として持つ置き場。

土台(`*_BASE`)は手で書く。特徴(`*_EXTRACTED`)は既存の話(`Episode`)の本文から
抽出して書き換える枠で、本文がまだ無いあいだは空。二つを足したものが
`*_STYLE_INSTRUCTION` で、プロンプトに埋めるのはこの定数の方。

共通(`SHARED_*`)はどの文にも効き、対象ごと(episode / plot / event / term)は
その対象の文にだけ足す。対象ごとの土台と特徴は共通とは別に持っているので、
あとから対象ごとに別の文面を用意できる。
"""
from __future__ import annotations

from dataclasses import dataclass

# 文体の特徴を抽出する材料にする、直近の話の本数。
STYLE_SOURCE_EPISODE_LIMIT = 10


@dataclass(frozen=True)
class StyleInstruction:
    """手で書く土台(`base`)と、本文から抽出した特徴(`extracted`)の対。"""

    base: str = ""
    extracted: str = ""

    @property
    def text(self) -> str:
        return "\n".join(part.strip() for part in (self.base, self.extracted) if part.strip())


# --- 共通(どの文にも効く文体) ---------------------------------------------

SHARED_STYLE_BASE = """\
語の選び方・文の運び方は、この世界の文章すべてで揃える。
一文を短く切り、修飾を重ねない。
抽象名詞で言い換えず、物と動作の名前で書く。
同じ語・同じ言い回しを近い距離で繰り返さない。"""

# 既存の話の本文から抽出した特徴。本文が溜まるたびにここだけを書き換える。
SHARED_STYLE_EXTRACTED = ""

SHARED_STYLE = StyleInstruction(base=SHARED_STYLE_BASE, extracted=SHARED_STYLE_EXTRACTED)


# --- 対象ごと --------------------------------------------------------------

EPISODE_STYLE_BASE = """\
本文は地の文と会話文を交ぜ、地の文に寄せすぎない。
情景は視点人物が実際に見聞きした範囲で書き、説明のための地の文を挟まない。
セリフは人物ごとの口調の差が読み分けられる長さで切る。"""

EPISODE_STYLE_EXTRACTED = ""

PLOT_STYLE_BASE = """\
筋書きは読ませる文ではなく、後から段階を測るための文として書く。
段階ごとに一〜二文で、誰と何を巡ってか分かる言い方にする。"""

PLOT_STYLE_EXTRACTED = ""

EVENT_STYLE_BASE = """\
出来事の記録は情景も語り口も持たせず、事実と関係だけで書く。
一文に一件だけ入れ、起きた順に並べる。"""

EVENT_STYLE_EXTRACTED = ""

TERM_STYLE_BASE = """\
語の説明は、その語を知らない読み手が一読で掴める短さにする。
物・制度・技のどれなのかを先に置き、来歴はその後に一文で足す。"""

TERM_STYLE_EXTRACTED = ""

STYLE_INSTRUCTIONS: dict[str, StyleInstruction] = {
    "episode": StyleInstruction(base=EPISODE_STYLE_BASE, extracted=EPISODE_STYLE_EXTRACTED),
    "plot": StyleInstruction(base=PLOT_STYLE_BASE, extracted=PLOT_STYLE_EXTRACTED),
    "event": StyleInstruction(base=EVENT_STYLE_BASE, extracted=EVENT_STYLE_EXTRACTED),
    "term": StyleInstruction(base=TERM_STYLE_BASE, extracted=TERM_STYLE_EXTRACTED),
}


def style_instruction(target: str) -> str:
    """`target`(episode / plot / event / term)の文へ埋め込む文体の指示。"""
    if target not in STYLE_INSTRUCTIONS:
        raise ValueError(f"文体の指示が無い対象: {target}")
    return "\n".join(
        text for text in (SHARED_STYLE.text, STYLE_INSTRUCTIONS[target].text) if text)


SHARED_STYLE_INSTRUCTION = SHARED_STYLE.text
EPISODE_STYLE_INSTRUCTION = style_instruction("episode")
PLOT_STYLE_INSTRUCTION = style_instruction("plot")
EVENT_STYLE_INSTRUCTION = style_instruction("event")
TERM_STYLE_INSTRUCTION = style_instruction("term")
