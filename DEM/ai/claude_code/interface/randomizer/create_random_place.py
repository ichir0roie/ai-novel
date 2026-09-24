#!/usr/bin/env python3
"""ランダムな場所の下書きを一件、辞書として作る、claude が呼ぶ入口。db には触れない。"""
from __future__ import annotations

from DEM.ai.claude_code.interface.randomizer._base import RandomDraft
from DEM.randomizer.random_location_generator import build_location


class CreateRandomPlace(RandomDraft):
    builder = staticmethod(build_location)
