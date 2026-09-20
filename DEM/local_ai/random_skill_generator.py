#!/usr/bin/env python3
"""**技(`Skill`)の下書きを、ローカルAI(`ai_client`)にまとめて量産させる。**

`DEM/local_ai/time_keepr/` の常駐系(時刻ロールで当たったら db へ確定まで
一気にやる)とは違い、こちらは呼び出し側が渡す `prompt`(どんな技を
量産したいか)と `count`(何件欲しいか)だけを受け取り、db には一切触れず
辞書のリストを返すだけの量産系。

`DEM/claude_interface/randomizer/commit_skill.CommitSkill` は技の下書き作成器を
まだ持たない(`IHG/` の方針通り、内容は手で決める想定だった)ので、ここで
埋める。db への確定は、返ってきた辞書をそのまま(または手直ししてから)
`CommitSkill` に渡す、呼び出し側の仕事のまま変えない。
"""
from __future__ import annotations

import random

from DEM.ai_instructions.naming import TERM_NAMING_INSTRUCTION
from DEM.ai_instructions.principles import AVOID_NARO_TEMPLATE_INSTRUCTION
from DEM.local_ai import ai_client

_SYSTEM_PROMPT = (
    "あなたは架空の世界観を構築する設定作家です。"
    "渡されたお題に沿う技(能力)を1件だけ考え、JSON で答えてください。"
    "キーは name(技名)、"
    "cost(発動コスト。1〜10の整数)、effect(効果。一言)、range(範囲。一言)、"
    "duration(持続時間。一言)、target(対象。一言)、"
    "constraint(制約・代償。一言)、text(technique の詳しい説明文)"
    "の八つだけ。" + TERM_NAMING_INSTRUCTION + AVOID_NARO_TEMPLATE_INSTRUCTION
)

_RANGE_CHOICES = ("自分のみ", "至近距離", "視界内", "触れた相手", "一帯")
_DURATION_CHOICES = ("瞬間", "数秒", "戦闘中のみ", "一日", "効果が切れるまで")
_TARGET_CHOICES = ("自分", "対象一人", "対象一体", "周囲一帯", "味方全体")


def _default_skill(rng: random.Random, n: int) -> dict:
    """AI の応答が壊れていたときに埋める、それらしい既定値。"""
    return {
        "name": f"仮の技{n}",
        "cost": rng.randint(1, 10),
        "effect": "",
        "range": rng.choice(_RANGE_CHOICES),
        "duration": rng.choice(_DURATION_CHOICES),
        "target": rng.choice(_TARGET_CHOICES),
        "constraint": "",
        "text": "",
    }


def generate_random(prompt: str, count: int) -> list[dict]:
    """`prompt` のお題に沿う技の下書きを `count` 件、辞書のリストで返す。

    db には一切触れない。一件ごとにローカルAIへ問い合わせ、応答が使えなかった
    件はそれらしい既定値のまま返す(`ai_client.try_generate_json` の流儀に合わせる)。
    """
    results: list[dict] = []
    for n in range(1, count + 1):
        seed = random.randrange(10 ** 9)
        rng = random.Random(seed)
        draft = _default_skill(rng, n)

        full_prompt = (
            f"お題: {prompt}\n"
            f"これは{count}件中{n}件目。既に出した技と被らない、新しい技を1件考えてください。"
        )
        decided = ai_client.try_generate_json(full_prompt, system=_SYSTEM_PROMPT)

        draft["name"] = decided.get("name") or draft["name"]
        draft["cost"] = int(decided.get("cost") or draft["cost"])
        draft["effect"] = decided.get("effect") or draft["effect"]
        draft["range"] = decided.get("range") or draft["range"]
        draft["duration"] = decided.get("duration") or draft["duration"]
        draft["target"] = decided.get("target") or draft["target"]
        draft["constraint"] = decided.get("constraint") or draft["constraint"]
        draft["text"] = decided.get("text") or draft["text"]

        print(f"[random_skill_generator] {n}/{count} 生成: {draft['name']}"
              f"(cost={draft['cost']}, effect={draft['effect'] or '(なし)'})")
        results.append(draft)

    return results
