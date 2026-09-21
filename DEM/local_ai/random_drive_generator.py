#!/usr/bin/env python3
"""人物の情動(`CharacterDrive`)の下書きを、ローカル AI にまとめて量産する。db には触れない。"""
from __future__ import annotations

import random

from IHG.ai_instructions.principles import AVOID_NARO_TEMPLATE_INSTRUCTION
from DEM.local_ai import ai_client

_SYSTEM_PROMPT = (
    "あなたは架空の世界観を構築する設定作家です。"
    "渡されたお題に沿う、人物が抱きうる情動(欲・恐れ・嘘・必要)を1件だけ"
    "考え、JSON で答えてください。キーは text(情動の中身。一言〜二言の"
    "自然な日本語)、level(その情動の強さ。1〜5の整数)の二つだけ。"
    + AVOID_NARO_TEMPLATE_INSTRUCTION
)

_LEVEL_RANGE = (1, 5)


def _default_drive(rng: random.Random, n: int) -> dict:
    """AI の応答が壊れていたときに埋める、それらしい既定値。"""
    return {
        "text": f"仮の情動{n}",
        "level": rng.randint(*_LEVEL_RANGE),
    }


def generate_random(prompt: str, count: int) -> list[dict]:
    """`prompt` のお題に沿う情動の下書きを `count` 件、辞書のリストで返す。応答が使えなかった件は既定値のまま返す。"""
    results: list[dict] = []
    for n in range(1, count + 1):
        seed = random.randrange(10 ** 9)
        rng = random.Random(seed)
        draft = _default_drive(rng, n)

        full_prompt = (
            f"お題: {prompt}\n"
            f"これは{count}件中{n}件目。既に出した情動と被らない、新しい情動を1件考えてください。"
        )
        decided = ai_client.try_generate_json(full_prompt, system=_SYSTEM_PROMPT)

        draft["text"] = decided.get("text") or draft["text"]
        draft["level"] = int(decided.get("level") or draft["level"])

        print(f"[random_drive_generator] {n}/{count} 生成: "
              f"{draft['text']}(level={draft['level']})")
        results.append(draft)

    return results
