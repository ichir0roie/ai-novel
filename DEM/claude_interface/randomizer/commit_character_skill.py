#!/usr/bin/env python3
"""JSON で受け取った「人物が技を持つ」ことを一件、db へ確定する、claude が呼ぶ入口。

出来事の結果として技が動いたときは `commit_event.CommitEvent` の
`character_skills` にまとめて乗せるが、既存の人物に**初期状態として**
技を持たせるなど、特定の出来事に紐づかない付与はここを使う。

`character_id` `skill_id`(`object_id` を渡す場合はそれも)の実在確認を
してから書き込む。スキーマに無い欄が混ざっていたら、そこで止める。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Character, CharacterSkill, Object, Skill
from DEM.db.schema_pydantic import to_dict


class CommitCharacterSkill(CommitDraft):
    """人物 ↔ 技の対応を一件、db へ確定して、格納後の中身を辞書で返す。

    `character_skill` は JSON 文字列でも辞書でもよい。`id` キーは無視する。
    """

    model = CharacterSkill

    def __init__(self, character_skill: str | dict):
        self.character_skill = character_skill

    def execute(self, session) -> dict:
        data = self.parse(self.character_skill)
        data.pop("id", None)
        self.check_columns(data)
        if data.get("skill_id") is None:
            raise ValueError("skill_id は必須")
        if data.get("character_id") is None:
            raise ValueError("character_id は必須")

        self.check_exists(session, Character, data.get("character_id"), "character_id")
        self.check_exists(session, Skill, data.get("skill_id"), "skill_id")
        self.check_exists(session, Object, data.get("object_id"), "object_id")

        record = CharacterSkill(**data)
        session.add(record)
        session.commit()
        return to_dict(record)
