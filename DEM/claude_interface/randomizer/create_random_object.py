#!/usr/bin/env python3
"""ランダムな個体(群)の下書きを一件、辞書として作る、claude が呼ぶ入口。db には触れない。"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import RandomDraft
from DEM.randomizer.random_object_generator import build_object


class CreateRandomObject(RandomDraft):
    builder = staticmethod(build_object)
