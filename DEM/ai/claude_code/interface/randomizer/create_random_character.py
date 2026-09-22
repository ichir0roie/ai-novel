#!/usr/bin/env python3
"""ランダムな人物の下書きを一件、辞書として作る、claude が呼ぶ入口。db には触れない。"""
from __future__ import annotations

from DEM.ai.claude_code.claude_interface.randomizer._base import RandomDraft
from DEM.randomizer.random_character_generator import build_character


class CreateRandomCharacter(RandomDraft):
    builder = staticmethod(build_character)
