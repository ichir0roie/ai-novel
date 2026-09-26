#!/usr/bin/env python3
"""土台(`*_BASE`)は手で書く。特徴(`*_EXTRACTED`)は既存の話(`Episode`)の本文から
抽出して書き換える枠で、本文がまだ無いあいだは空。

対象ごとの土台と特徴は共通とは別に持っているので、あとから対象ごとに別の文面を用意できる。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 文体の特徴を抽出する材料にする、直近の話の本数。
STYLE_SOURCE_EPISODE_LIMIT = 10

# 一話ぶんの本文の目安。
EPISODE_TARGET_LETTERS = (5000, 8000)

# 話と同じ小説の形で書く出来事の本文(毎日のルーチン)の目安。一話の三分の一。
EVENT_NOVEL_TARGET_LETTERS = tuple(int(round(letters / 3, -2)) for letters in EPISODE_TARGET_LETTERS)

# 生成のときに場面の切れ目へ置かせる行。`layout_novel_text` が空行二つに置き換える。
SCENE_BREAK = "◇"

# 一行がこの字数を超えるときは、文の切れ目か読点で折り返す。
LINE_LETTERS = 50

_SENTENCE_END = "。！？!?"
_COMMA = "、"
_QUOTE_OPEN = "「『"
_QUOTE_CLOSE = "」』"


def _quote_depth(text: str, depth: int = 0) -> int:
    for char in text:
        if char in _QUOTE_OPEN:
            depth += 1
        elif char in _QUOTE_CLOSE:
            depth = max(depth - 1, 0)
    return depth


# 折り返した行(「」が閉じていない行・読点で終わる行)は、前の行へつなぎ直してから整える。
def _join_wrapped_lines(lines: list[str]) -> list[str]:
    joined, depth = [], 0
    for line in (line.strip() for line in lines):
        if joined and (depth > 0 or joined[-1].endswith(_COMMA)):
            joined[-1] += line
        else:
            joined.append(line)
        depth = _quote_depth(line, depth)
    return joined


def _cut_after(text: str, marks: str) -> list[str]:
    pieces, current = [], ""
    for index, char in enumerate(text):
        current += char
        following = text[index + 1:index + 2]
        if char in marks and following and following not in marks + _QUOTE_CLOSE:
            pieces.append(current)
            current = ""
    if current:
        pieces.append(current)
    return pieces


def _wrap(sentence: str) -> list[str]:
    if len(sentence) <= LINE_LETTERS:
        return [sentence]
    pieces = [part for piece in _cut_after(sentence, _SENTENCE_END)
              for part in (_cut_after(piece, _COMMA) if len(piece) > LINE_LETTERS else [piece])]
    lines = [""]
    for piece in pieces:
        if lines[-1] and len(lines[-1]) + len(piece) > LINE_LETTERS:
            lines.append(piece)
        else:
            lines[-1] += piece
    return lines


def _split_sentences(line: str) -> list[str]:
    sentences, current, depth = [], "", 0
    for index, char in enumerate(line):
        current += char
        if char in _QUOTE_OPEN:
            depth += 1
        elif char in _QUOTE_CLOSE:
            depth = max(depth - 1, 0)
        elif depth == 0 and char in _SENTENCE_END:
            following = line[index + 1:index + 2]
            if following and following in _SENTENCE_END + _QUOTE_CLOSE:
                continue
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())
    return sentences


# 空行一つは話し手や流れの切れ目、空行二つ以上と「◇」の行は場面の切れ目として読む。
# 読点も文の切れ目も無い長い文は、折り返さずに残す。
def layout_novel_text(text: str) -> str:
    scenes = []
    marked = re.sub(rf"^[ \t　]*{SCENE_BREAK}[ \t　]*$", "\n\n\n", text.replace("\r\n", "\n"), flags=re.M)
    for scene in re.split(r"\n[ \t　]*\n(?:[ \t　]*\n)+", marked.strip()):
        if not scene.strip():
            continue
        beats = [beat for beat in re.split(r"\n[ \t　]*\n", scene.strip()) if beat.strip()]
        scenes.append("\n\n".join(
            "\n".join(wrapped for line in _join_wrapped_lines(beat.splitlines())
                      for sentence in _split_sentences(line) for wrapped in _wrap(sentence))
            for beat in beats))
    return "\n\n\n".join(scenes)


@dataclass(frozen=True)
class StyleInstruction:
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

舞台は西暦一万年ごろの SF 世界。英語由来のカタカナ語(チーム・リーダーなど)は日常の語としてそのまま使う。
古い日本語の言い回し(仲間の集まりを「一党」と呼ぶなど)は、古代の表現として、古い文献や古風な人物の口にだけ出す。
「盗賊一党」のような悪党の集まりの呼び方は、そのまま使ってよい。

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
地の文は一文ごとに改行する。セリフは、中に文がいくつあっても「」ごと一行にする(長い行は清書のときに折り返される)。
空行は、話し手や流れが変わるところにだけ一つ置き、ほかでは空けない。
一人の人物の言動が続くあいだは、そのセリフと、誰が言ったか・どう動いたかの地の文を、空行を挟まず改行だけで続ける。
描写の細かさは中身の重さで変える。筋が動くところ・人物の気持ちが揺れるところは、動作・セリフ・間を一つずつ追って細かく書く。
移動・待ち時間・繰り返しの作業のように筋が動かないところは、一〜二文で飛ばす。
情景は、視点人物の目に留まった物を一か所に一つか二つだけ書き、見えるものを並べ立てない。
気持ちは地の文で説明しきらず、動作・セリフに出す分と、書かずに読み手へ預ける分を分ける。
締め方は、書いている出来事の中身が終わったかどうかで変える。
中身が終わっていないときは、謎・伏線・この先への期待を残して切る。
中身が終わったときは、余韻を残すか、気の利いた落ちを付けて締める。"""


def _scale_rule(unit: str, letters: tuple[int, int]) -> str:
    return f"""\
{unit}は{letters[0]}〜{letters[1]}字。
場面の数と一場面の長さは決めず、中身に合わせる。場面が変わる(場所・時間・書く対象が変わる)ところにだけ、「{SCENE_BREAK}」だけの行を置く。
字数は、実際に起きることで作る。修飾・言い換え・心情の反芻を足して伸ばさない。"""


EPISODE_STYLE_BASE = f"""\
{NOVEL_STYLE_BASE}
{_scale_rule("一話", EPISODE_TARGET_LETTERS)}
種(key)に場面が足りないときは、足りないぶんを場面として立ててから書く。"""

EPISODE_STYLE_EXTRACTED = """\
括弧の例は直す向きを示すもので、言い回し・場面を本文へ流用しない。
セリフは話し言葉で書く。書き言葉の丁寧さへ寄せず、崩した言い方・呼びかけを使う(「ほんとうに」より「ほんとに」、「言ってください」より「おしえてよ」)。
問いには「？」、強い感情には「！」、言い淀みには「…」を置き、句点や言い切りに含ませない。
同じ言葉を受けて返す応酬は、そのままなぞらない。なぞるなら「？」と「。」で問いと答えの差を付ける(「翼も？」「翼も。」)。
一言ずつのセリフを何往復も続けない。一つのセリフに、相手への返事とその人物が言いたいことを一緒に持たせて、往復の数を減らす(「大きい」「二年は着られるの」「今年は?」「今年も着られるでしょう」より「母さま、これ大きいよ。袖が手より長い」「二年は着られるの。袖を折れば、今年だって着られるでしょう」)。
セリフで理屈を積み上げて説明しない。短く言い切り、相手には理屈ではなく感情で返させる。
人物の言動で表せるところは、積極的にセリフにする。視点人物のひとりの場面でも、段取りや内心を地の文で説明せず、独り言として口に出させる(「報告書はまだ書いていない。どうせいつも誤魔化して書いているだけだし。」より「ふぅ、やっとついた…。報告書は、…あとでいいか。どうせいつも誤魔化しているだけだし。」)。
地の文の独白は、視点人物がその場で思った言葉のまま書く。比喩や警句・一般論へ言い換えず、好き・困ったといった感情を隠さない(「これがこんなに大きいものだと忘れている」より「こんなに大きかったっけ」)。
制度や事務の側に立つ人物の口調だけは硬いまま残し、人間の口調との差を広げる。
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
{_scale_rule("出来事一件", EVENT_NOVEL_TARGET_LETTERS)}"""

STORY_STYLE_BASE = """\
作品の筋書きは読ませる文ではなく、後から段階を測るための文として書く。
段階ごとに一〜二文で、誰と何を巡ってか分かる言い方にする。"""

STORY_STYLE_EXTRACTED = ""

EVENT_STYLE_BASE = """\
出来事の記録は情景も語り口も持たせず、事実と関係だけで書く。
一文に一件だけ入れ、起きた順に並べる。"""

EVENT_STYLE_EXTRACTED = ""

IDEA_STYLE_BASE = """\
アイデアの説明は、それを知らない読み手が一読で掴める短さにする。
物・制度・技のどれなのかを先に置き、来歴はその後に一文で足す。"""

IDEA_STYLE_EXTRACTED = ""

STYLE_INSTRUCTIONS: dict[str, StyleInstruction] = {
    "episode": StyleInstruction(base=EPISODE_STYLE_BASE, extracted=EPISODE_STYLE_EXTRACTED),
    "event_novel": StyleInstruction(base=EVENT_NOVEL_STYLE_BASE, extracted=EPISODE_STYLE_EXTRACTED),
    "story": StyleInstruction(base=STORY_STYLE_BASE, extracted=STORY_STYLE_EXTRACTED),
    "event": StyleInstruction(base=EVENT_STYLE_BASE, extracted=EVENT_STYLE_EXTRACTED),
    "idea": StyleInstruction(base=IDEA_STYLE_BASE, extracted=IDEA_STYLE_EXTRACTED),
}


def style_instruction(target: str) -> str:
    if target not in STYLE_INSTRUCTIONS:
        raise ValueError(f"文体の指示が無い対象: {target}")
    return "\n".join(
        text for text in (SHARED_STYLE.text, STYLE_INSTRUCTIONS[target].text) if text)


SHARED_STYLE_INSTRUCTION = SHARED_STYLE.text
EPISODE_STYLE_INSTRUCTION = style_instruction("episode")
EVENT_NOVEL_STYLE_INSTRUCTION = style_instruction("event_novel")
STORY_STYLE_INSTRUCTION = style_instruction("story")
EVENT_STYLE_INSTRUCTION = style_instruction("event")
IDEA_STYLE_INSTRUCTION = style_instruction("idea")
