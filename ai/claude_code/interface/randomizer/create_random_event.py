#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code.interface.randomizer._base import RandomDraft
from randomizer.random_event_generator import build_event


class CreateRandomEvent(RandomDraft):
    builder = staticmethod(build_event)
