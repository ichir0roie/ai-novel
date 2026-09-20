#!/usr/bin/env python3
"""JSON で受け取った内容で、**既にある**人物を一件、db 上で直す、claude が呼ぶ入口。

新しく人物を作るのは `commit_character.CommitCharacter` の仕事。ここは、既に
確定済みの人物の欄(`text` の書き直しなど)を後から直すためだけの入口——
`id` で対象を指定し、渡した欄だけを上書きする(渡さなかった欄はそのまま)。

`id` の実在確認と、スキーマに無い欄の混入チェックは他の「確定する」入口と同じ。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Character
from DEM.db.schema_pydantic import to_dict


class UpdateCharacter(CommitDraft):
    """人物を一件、渡した欄だけ書き換えて db へ確定し、格納後の中身を返す。

    `character` は JSON 文字列でも辞書でもよい。`id` は直す対象を指すので
    必須(`commit_character.CommitCharacter` と違い、ここでは無視しない)。
    """

    model = Character

    def __init__(self, character: str | dict):
        self.character = character

    def execute(self, session) -> dict:
        data = self.parse(self.character)
        character_id = data.pop("id", None)
        if character_id is None:
            raise ValueError("id は必須(直す対象の人物)")
        self.check_columns(data)

        record = session.get(Character, character_id)
        if record is None:
            raise ValueError(f"id={character_id} という人物が見つからない")

        for key, value in data.items():
            setattr(record, key, value)
        session.commit()
        return to_dict(record)
