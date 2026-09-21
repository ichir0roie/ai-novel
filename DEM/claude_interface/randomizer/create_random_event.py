#!/usr/bin/env python3
"""ランダムな出来事の下書きを一件、辞書として作る、claude が呼ぶ入口。db には触れない。"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import RandomDraft
from DEM.randomizer.random_event_generator import build_event


class CreateRandomEvent(RandomDraft):
    builder = staticmethod(build_event)
