#!/usr/bin/env python3
"""JSON で受け取った人物の情動(欲・恐れ・嘘・必要)を一件、db へ確定する、
claude が呼ぶ入口。

出来事の結果として情動が動いたときは `commit_event.CommitEvent` の
`character_drives` にまとめて乗せるが、既存の人物に**初期状態として**
情動を持たせるなど、特定の出来事に紐づかない付与はここを使う。

`character_id` の実在確認をしてから書き込む。スキーマに無い欄が
混ざっていたら、そこで止める。`text` は必須。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Character, CharacterEmotion
from DEM.db.schema_pydantic import to_dict


class CommitCharacterDrive(CommitDraft):
    """人物の情動を一件、db へ確定して、格納後の中身を辞書で返す。

    `drive` は JSON 文字列でも辞書でもよい。`id` キーは無視する。
    """

    model = CharacterEmotion

    def __init__(self, drive: str | dict):
        self.drive = drive

    def execute(self, session) -> dict:
        data = self.parse(self.drive)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("text"):
            raise ValueError("text は必須")
        if data.get("character_id") is None:
            raise ValueError("character_id は必須")

        self.check_exists(session, Character, data.get("character_id"), "character_id")

        record = CharacterEmotion(**data)
        session.add(record)
        session.commit()
        return to_dict(record)
