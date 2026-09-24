#!/usr/bin/env python3
"""ミームを一件、db から削除する、claude が呼ぶ入口。"""
from __future__ import annotations

from ai.claude_code.interface._base import UnknownRecordError
from ai.claude_code.interface.randomizer._base import CommitDraft
from db.schema import Meme


class DeleteMeme(CommitDraft):
    """ミームを一件削除して、消す直前の中身を辞書で返す。"""

    model = Meme

    def __init__(self, meme_id: int):
        self.meme_id = meme_id

    def execute(self, session) -> dict:
        record = session.get(Meme, int(self.meme_id))
        if record is None:
            raise UnknownRecordError(f"meme_id={self.meme_id} という id の meme が見つからない")

        data = {"id": record.id, "category": record.category, "text": record.text}
        session.delete(record)
        return data
