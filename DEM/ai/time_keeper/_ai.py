#!/usr/bin/env python3
"""生成器が AI に求める顔。`DEM/ai/local_ai/ai_client.py` と `DEM/ai/claude_code/ai_client.py` はどちらもこの形を満たす。"""
from __future__ import annotations

from typing import Protocol


class AIClient(Protocol):
    def try_generate_json(
        self,
        prompt: str,
        schema: dict,
        *,
        system: str | None = None,
        timeout: float = 120.0,
        options: dict | None = None,
    ) -> dict: ...
