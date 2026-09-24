#!/usr/bin/env python3
"""既にあるミームを一件、渡した欄だけ db 上で直す、claude が呼ぶ入口。"""
from __future__ import annotations

from ai.claude_code.interface._base import UnknownRecordError
from ai.claude_code.interface.randomizer._base import CommitDraft
from db.schema import MEME_CATEGORIES, Meme
from db.schema_pydantic import to_dict


class UpdateMeme(CommitDraft):
    model = Meme

    def __init__(self, meme: str | dict):
        self.meme = meme

    def execute(self, session) -> dict:
        data = self.parse(self.meme)
        meme_id = data.pop("id", None)
        if meme_id is None:
            raise ValueError("id は必須(直す対象のミーム)")
        self.check_columns(data)
        if data.get("category") not in (None, *MEME_CATEGORIES):
            raise ValueError(f"category は {'/'.join(MEME_CATEGORIES)} のいずれか: {data['category']}")

        record = session.get(Meme, meme_id)
        if record is None:
            raise UnknownRecordError(f"id={meme_id} というミームが見つからない")

        for key, value in data.items():
            setattr(record, key, value)
        self.finalize(session, record)
        return to_dict(record)
