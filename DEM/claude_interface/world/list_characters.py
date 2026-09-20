#!/usr/bin/env python3
"""**人物の一覧**を出す、claude が呼ぶ入口。

既存の人物を db 横断で見渡すのに使う(id 一件を時刻付きで読むのは
`story.read_character.ReadCharacter` の仕事)。技・情動を持つかどうかも
一緒に返すので、まだ付与していない人物を拾い出すのに使える。db には
書き込まない。
"""
from __future__ import annotations

from DEM.claude_interface.world._base import WorldQuery
from DEM.data_access_logic.query import common_query
from DEM.db.schema_pydantic import relation_names


class ListCharacters(WorldQuery):
    """人物を一覧で返す。"""

    def select(self):
        return common_query.characters_select()

    def row(self, row) -> dict:
        return {
            "id": row.id, "name": row.name, "text": row.text,
            "sex": row.sex, "tone": row.tone,
            "born_place_id": row.born_place_id, "belong_id": row.belong_id,
            "kind_id": row.kind_id,
            "skill_ids": [skill.skill_id for skill in row.skills],
            "emotion_count": len(row.emotions),
            **relation_names(row, ["kind"]),
        }
