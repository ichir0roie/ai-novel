#!/usr/bin/env python3
"""AI を呼ばずに、渡された JSON Schema の形だけを満たす値を返す `AIClient`。

生成器の流れ(db への確定・時刻の進み・busy の除外など)を、AI 無し・費用無しで
最後まで通すためのもの。文章はすべて「モック…」の埋め草になる。
"""
from __future__ import annotations

import random
import re

_CHARACTER_ID_IN_PROMPT = re.compile(r"'character_id': (\d+)")

# 空だと後段が何もしない配列だけ、件数を持たせる。それ以外の配列は空で返す。
_ARRAY_SIZES = {"candidates": 3, "seeds": 2}


class MockAIClient:
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.calls: list[dict] = []

    def try_generate_json(
        self, prompt: str, schema: dict, *,
        system: str | None = None, timeout: float = 120.0, options: dict | None = None,
    ) -> dict:
        self.calls.append({"prompt": prompt, "system": system, "schema": schema})
        return self._fill(schema, prompt, key=None)

    def usage_summary(self) -> str:
        return f"mock 呼び出し {len(self.calls)}回"

    def _fill(self, schema: dict, prompt: str, key: str | None):
        types = schema.get("type")
        if isinstance(types, list):
            if "null" in types:
                return None
            types = types[0]
        if "enum" in schema:
            return self.rng.choice(schema["enum"])
        if types == "object":
            return {name: self._fill(sub, prompt, name)
                    for name, sub in schema.get("properties", {}).items()}
        if types == "array":
            if key == "character_ids":
                ids = sorted({int(m) for m in _CHARACTER_ID_IN_PROMPT.findall(prompt)})
                return self.rng.sample(ids, min(len(ids), self.rng.randint(1, 2))) if ids else []
            item = schema.get("items", {"type": "string"})
            return [self._fill(item, prompt, key) for _ in range(_ARRAY_SIZES.get(key or "", 0))]
        if types == "integer":
            low = schema.get("minimum", 1)
            high = schema.get("maximum", max(low, 1))
            return self.rng.randint(low, high)
        if types == "number":
            return float(schema.get("minimum", 0))
        if types == "boolean":
            return False
        return f"モック{key or ''}{len(self.calls)}"
