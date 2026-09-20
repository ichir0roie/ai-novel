#!/usr/bin/env python3
"""JSON で受け取った技(能力そのものの定義)を一件、db へ確定する、claude が呼ぶ入口。

`Skill` は技のカタログ本体(名前・コスト・効果・範囲・持続時間・対象・制約)。
誰が持つかは別の入口 `commit_character_skill.CommitCharacterSkill` が
`CharacterSkill` へ紐づける。技はランダム生成の対になる下書き作成器を
まだ持たないので、ここでは辞書をそのまま受け取って確定するだけにとどめる
(内容は `IHG/` の方針に沿って手で決める)。

スキーマに無い欄が混じっていたら(`DEM/db/schema.py` の `Skill` の列と
照らして)そこで止める。`name` `effect` `text`(`MarkdownBase` 由来。技の説明)は必須。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import Skill
from DEM.db.schema_pydantic import to_dict


class CommitSkill(CommitDraft):
    """技を一件、db へ確定して、格納後の中身を辞書で返す。

    `skill` は JSON 文字列でも辞書でもよい。`id` キーは無視する
    (採番は db に任せる)。
    """

    model = Skill

    def __init__(self, skill: str | dict):
        self.skill = skill

    def execute(self, session) -> dict:
        data = self.parse(self.skill)
        data.pop("id", None)
        self.check_columns(data)
        if not data.get("name"):
            raise ValueError("name は必須")
        if not data.get("effect"):
            raise ValueError("effect は必須")
        if not data.get("text"):
            raise ValueError("text は必須")

        record = Skill(**data)
        session.add(record)
        session.commit()
        return to_dict(record)
