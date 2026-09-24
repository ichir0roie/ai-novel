#!/usr/bin/env python3
"""人物・対象に持たせるミームを、分類ごとに引いて古今表裏を割り振る、claude が呼ぶ入口。db には書かない。

    DrawMemes(person=True, seed=None).run()   [{"position", "id", "category", "text"}, ...]
"""
from __future__ import annotations

import random

from ai.claude_code.interface._base import SessionEntrypoint
from ai.time_keeper import constants
from ai.time_keeper import meme as _meme

__all__ = ["DrawMemes"]


class DrawMemes(SessionEntrypoint):
    """人物なら `constants.MEME_PERSON_CATEGORIES`、人物以外の対象なら `MEME_NON_PERSON_CATEGORIES` の分類から引く。"""

    def __init__(self, person: bool = True, seed: int | None = None):
        self.person = person
        self.seed = seed

    def execute(self, session) -> list[dict]:
        categories = constants.MEME_PERSON_CATEGORIES if self.person else constants.MEME_NON_PERSON_CATEGORIES
        return _meme.draw(session, random.Random(self.seed), categories)
