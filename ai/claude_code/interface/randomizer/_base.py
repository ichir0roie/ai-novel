#!/usr/bin/env python3
from __future__ import annotations

from ai.claude_code import ai_client
from ai.claude_code.interface._base import CommitEntrypoint, Entrypoint
from ai.time_keeper import meme
from db.schema import get_env_session


class RandomDraft(Entrypoint):
    builder: staticmethod

    def __init__(self, **overrides):
        self.overrides = overrides

    def run(self) -> dict:
        return self.builder(**self.overrides)


class CommitDraft(CommitEntrypoint):
    pass


class CommitMemeSource(CommitDraft):
    """ミームの元(アイデア・oracle)を確定したあと、その場でミームを抜き出す基底。

    抜き出しは確定のトランザクションを閉じてから行う(AI が答えなくても確定は残し、
    `meme_seeded` が false のまま次の抽出に回す)。足したミームの件数を `memes_added` で返す。
    """

    def run(self) -> dict:
        result = super().run()
        with get_env_session() as session:
            result["memes_added"] = meme.refresh(session, ai_client)
        return result
