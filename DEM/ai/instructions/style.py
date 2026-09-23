#!/usr/bin/env python3
"""文体の特徴を、プロンプトへ埋め込める定数として持つ置き場。

土台(`*_BASE`)は手で書く。特徴(`*_EXTRACTED`)は既存の話(`Episode`)の本文から
抽出して書き換える枠で、本文がまだ無いあいだは空。二つを足したものが
`*_STYLE_INSTRUCTION` で、プロンプトに埋めるのはこの定数の方。

共通(`SHARED_*`)はどの文にも効き、対象ごと(episode / story / event / term)は
その対象の文にだけ足す。対象ごとの土台と特徴は共通とは別に持っているので、
あとから対象ごとに別の文面を用意できる。
"""
from __future__ import annotations

from dataclasses import dataclass

# 文体の特徴を抽出する材料にする、直近の話の本数。
STYLE_SOURCE_EPISODE_LIMIT = 10

# 一話ぶんの本文の目安。長さは場面の数で作るので、場面の側にも目安を持つ。
EPISODE_TARGET_LETTERS = (5000, 8000)
EPISODE_TARGET_SCENES = (4, 6)
EPISODE_TARGET_SCENE_LETTERS = (1200, 1600)

# 場面の切れ目に置く行。
SCENE_BREAK = "◇"


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
修飾を重ねない。抽象名詞で言い換えず、物と動作の名前で書く。
同じ語・同じ言い回しを近い距離で繰り返さない。

基本的な文体はライトノベルを参考にする。

"""

# 既存の話の本文から抽出した特徴。本文が溜まるたびにここだけを書き換える。
SHARED_STYLE_EXTRACTED = ""

SHARED_STYLE = StyleInstruction(base=SHARED_STYLE_BASE, extracted=SHARED_STYLE_EXTRACTED)


# --- 対象ごと --------------------------------------------------------------

EPISODE_STYLE_BASE = f"""\
本文は地の文と会話文を交ぜ、地の文に寄せすぎない。
情景は視点人物が実際に見聞きした範囲で書き、説明のための地の文を挟まない。
セリフは人物ごとの口調の差が読み分けられる長さで切る。
空行は、言動の主体が変わるとき・場面が動くとき(時間が飛ぶ、場所が移る、人物から視点が外れる)・一行だけを孤立させて間を作るときにだけ置く。
一人の人物の言動が続くあいだは、そのセリフと、誰が言ったか・どう動いたかの地の文を、空行を挟まず改行だけで続ける。
孤立させた一行は間を作るための道具なので、一話に数回までに抑える。
一話は{EPISODE_TARGET_LETTERS[0]}〜{EPISODE_TARGET_LETTERS[1]}字。\
{EPISODE_TARGET_SCENES[0]}〜{EPISODE_TARGET_SCENES[1]}個の場面に分け、\
一場面は{EPISODE_TARGET_SCENE_LETTERS[0]}〜{EPISODE_TARGET_SCENE_LETTERS[1]}字を目安にする。
場面は「どこで・誰が・何が変わるか」が一つ決まる単位で、切れ目には「{SCENE_BREAK}」だけの行を置く。
字数は場面の数と、その場面で実際に起きることで作る。修飾・言い換え・心情の反芻を足して伸ばさない。
種(key)に場面が足りないときは、足りないぶんを場面として立ててから書く。"""

EPISODE_STYLE_EXTRACTED = ""

STORY_STYLE_BASE = """\
作品の筋書きは読ませる文ではなく、後から段階を測るための文として書く。
段階ごとに一〜二文で、誰と何を巡ってか分かる言い方にする。"""

STORY_STYLE_EXTRACTED = ""

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
    "story": StyleInstruction(base=STORY_STYLE_BASE, extracted=STORY_STYLE_EXTRACTED),
    "event": StyleInstruction(base=EVENT_STYLE_BASE, extracted=EVENT_STYLE_EXTRACTED),
    "term": StyleInstruction(base=TERM_STYLE_BASE, extracted=TERM_STYLE_EXTRACTED),
}


def style_instruction(target: str) -> str:
    """`target`(episode / story / event / term)の文へ埋め込む文体の指示。"""
    if target not in STYLE_INSTRUCTIONS:
        raise ValueError(f"文体の指示が無い対象: {target}")
    return "\n".join(
        text for text in (SHARED_STYLE.text, STYLE_INSTRUCTIONS[target].text) if text)


SHARED_STYLE_INSTRUCTION = SHARED_STYLE.text
EPISODE_STYLE_INSTRUCTION = style_instruction("episode")
STORY_STYLE_INSTRUCTION = style_instruction("story")
EVENT_STYLE_INSTRUCTION = style_instruction("event")
TERM_STYLE_INSTRUCTION = style_instruction("term")
