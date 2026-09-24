#!/usr/bin/env python3
"""文体の特徴を、プロンプトへ埋め込める定数として持つ置き場。

土台(`*_BASE`)は手で書く。特徴(`*_EXTRACTED`)は既存の話(`Episode`)の本文から
抽出して書き換える枠で、本文がまだ無いあいだは空。二つを足したものが
`*_STYLE_INSTRUCTION` で、プロンプトに埋めるのはこの定数の方。

共通(`SHARED_*`)はどの文にも効き、対象ごと(episode / event_novel / story / event / term)は
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

# 話と同じ小説の形で書く出来事の本文(毎日のルーチン)の目安。一話の三分の一。
EVENT_NOVEL_TARGET_LETTERS = tuple(int(round(letters / 3, -2)) for letters in EPISODE_TARGET_LETTERS)
EVENT_NOVEL_TARGET_SCENES = tuple(max(1, round(scenes / 3)) for scenes in EPISODE_TARGET_SCENES)

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
SHARED_STYLE_EXTRACTED = """\
語は日常でそのまま通じるものを選び、硬い制度語・古い言い回しへ寄せない
(「届け出る」より「報告する」、「体を持たない」より「実体を持たない」)。
世界の仕掛けに掛かる語だけは、噛み砕いた言い換えへ逃げずにそのまま書く
(「生きものの釣り合い」より「遺伝情報の均衡」)。
一般的な表現には簡単な漢字を使う。
"""

SHARED_STYLE = StyleInstruction(base=SHARED_STYLE_BASE, extracted=SHARED_STYLE_EXTRACTED)


# --- 対象ごと --------------------------------------------------------------

# 話と、話と同じ小説の形で書く出来事の本文とに共通する書き方。分量は `_scale_rule` で足す。
NOVEL_STYLE_BASE = """\
本文は地の文と会話文を交ぜ、地の文に寄せすぎない。
情景は視点人物が実際に見聞きした範囲で書き、説明のための地の文を挟まない。
セリフは人物ごとの口調の差が読み分けられる長さで切る。
空行は、言動の主体が変わるとき・場面が動くとき(時間が飛ぶ、場所が移る、人物から視点が外れる)・一行だけを孤立させて間を作るときにだけ置く。
一人の人物の言動が続くあいだは、そのセリフと、誰が言ったか・どう動いたかの地の文を、空行を挟まず改行だけで続ける。"""


def _scale_rule(unit: str, letters: tuple[int, int], scenes: tuple[int, int]) -> str:
    """`unit`(「一話」など)一つぶんの分量と、場面の切り方。"""
    return f"""\
孤立させた一行は間を作るための道具なので、{unit}に数回までに抑える。
{unit}は{letters[0]}〜{letters[1]}字。\
{scenes[0]}〜{scenes[1]}個の場面に分け、\
一場面は{EPISODE_TARGET_SCENE_LETTERS[0]}〜{EPISODE_TARGET_SCENE_LETTERS[1]}字を目安にする。
場面は「どこで・誰が・何が変わるか」が一つ決まる単位で、切れ目には「{SCENE_BREAK}」だけの行を置く。
字数は場面の数と、その場面で実際に起きることで作る。修飾・言い換え・心情の反芻を足して伸ばさない。"""


EPISODE_STYLE_BASE = f"""\
{NOVEL_STYLE_BASE}
{_scale_rule("一話", EPISODE_TARGET_LETTERS, EPISODE_TARGET_SCENES)}
種(key)に場面が足りないときは、足りないぶんを場面として立ててから書く。"""

EPISODE_STYLE_EXTRACTED = """\
セリフは話し言葉で書く。書き言葉の丁寧さへ寄せず、崩した言い方・呼びかけを使う(「ほんとうに」より「ほんとに」、「言ってください」より「おしえてよ」)。
問いには「？」、強い感情には「！」、言い淀みには「…」を置き、句点や言い切りに含ませない。
同じ言葉を受けて返す応酬は、そのままなぞらない。なぞるなら「？」と「。」で問いと答えの差を付ける(「翼も？」「翼も。」)。
セリフで理屈を積み上げて説明しない。短く言い切り、相手には理屈ではなく感情で返させる。
地の文の独白は、視点人物がその場で思った言葉のまま書く。比喩や警句・一般論へ言い換えず、好き・困ったといった感情を隠さない(「これがこんなに大きいものだと忘れている」より「こんなに大きかったっけ」)。
制度や事務の側に立つ人物の口調だけは硬いまま残し、人間の口調との差を広げる。
話を締める一行に、気の利いた落ちを付けない。
題は詩的な体言止めへ寄せず、人物の言葉に近い言い回しにする(「堕ちる翼」より「翼は捨てて」)。
設定や制度は、察させる言い方に寄せず、その場の人物が分かる言葉で言い切らせる(「この部屋の記録は、局の様式に無い」より「この部屋の会話は記録されない」)。
「AではなくBだ」の対句で決めない。整った言い換えより、話者がそう思っていることをそのまま言わせる(「規格の外じゃない。規格より前だ」より「規格なんて問題じゃない」)。
通達・処分のような事務の文は、一文ずつ改行で切り、一段落に詰めない。
報せを受けた衝撃は、内心の説明を重ねずに動作ひとつで書く(「二度読んだ」「三度目を読もうとして、やめた」より「握りしめた」)。
詫び・戸惑いはセリフに出させ、地の文の説明へ回さない(「順序が逆になった」より「順序が逆になってしまった。すまない」)。
幼い子のセリフは、その年齢で使う短い形にする(「痛くなかった?」より「痛い?」)。
行き先や事情を聞かれたら、一語で突き放さず、これからどうするかまで答えさせる(「家を探す」より「これから生きていくところ。まずは家を探しましょう」)。
事務の側の人物の決まり文句は、話をまたいで同じ言い方で繰り返す。あとの話で別の人物がそれを返すと効く(ピリムの「欄を埋める」→アウレアの「埋めるな」)。"""

# 話と同じ小説の形で書く出来事の本文(毎日のルーチン)。特徴は話のもの(EPISODE_STYLE_EXTRACTED)を使う。
EVENT_NOVEL_STYLE_BASE = f"""\
{NOVEL_STYLE_BASE}
{_scale_rule("出来事一件", EVENT_NOVEL_TARGET_LETTERS, EVENT_NOVEL_TARGET_SCENES)}"""

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
    "event_novel": StyleInstruction(base=EVENT_NOVEL_STYLE_BASE, extracted=EPISODE_STYLE_EXTRACTED),
    "story": StyleInstruction(base=STORY_STYLE_BASE, extracted=STORY_STYLE_EXTRACTED),
    "event": StyleInstruction(base=EVENT_STYLE_BASE, extracted=EVENT_STYLE_EXTRACTED),
    "term": StyleInstruction(base=TERM_STYLE_BASE, extracted=TERM_STYLE_EXTRACTED),
}


def style_instruction(target: str) -> str:
    """`target`(episode / event_novel / story / event / term)の文へ埋め込む文体の指示。"""
    if target not in STYLE_INSTRUCTIONS:
        raise ValueError(f"文体の指示が無い対象: {target}")
    return "\n".join(
        text for text in (SHARED_STYLE.text, STYLE_INSTRUCTIONS[target].text) if text)


SHARED_STYLE_INSTRUCTION = SHARED_STYLE.text
EPISODE_STYLE_INSTRUCTION = style_instruction("episode")
EVENT_NOVEL_STYLE_INSTRUCTION = style_instruction("event_novel")
STORY_STYLE_INSTRUCTION = style_instruction("story")
EVENT_STYLE_INSTRUCTION = style_instruction("event")
TERM_STYLE_INSTRUCTION = style_instruction("term")
