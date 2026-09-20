#!/usr/bin/env python3
"""JSON で受け取った出来事を一件、db へ確定する、claude が呼ぶ入口。

`CreateRandomEvent` が返した辞書を claude が文脈に合わせて書き換えた
ものを受け取る想定。db に触れるのはこのモジュールだけ——
`create_random_event` 側は一切 db を見ない。

実在レコードを指す欄(`location_id` `character_ids` `object_ids`
`parent_event_id`)は、渡された id が db に実在するかをここで確かめてから
書き込む。`character_ids` `object_ids` は id のリスト(多対多。何人・
何個体でも渡せる。省けば空の一覧のまま)で、`event_character` `event_object`
(中間テーブル)へ一件ずつ書き込む。`name` と `time` は必須。
スキーマに無い欄が混じっていたら(`DEM/db/schema.py` の `Event` の列と
照らして)そこで止める。

出来事が人物の情動・技を動かしたときは、`character_drives` `character_skills`
にその変化も乗せて渡す。**出来事の確定と同じ書き込みでまとめて確定する**
(情動・技だけを後から別の入口で直すのではなく、その出来事が起きた結果として
一緒に記録する)。

- `character_drives`: `[{character_id, text, level, start?, end?}, ...]`。
  一件ごとに `CharacterDrive`(テーブル名は `character_drive`)を一件足す
- `character_skills`: `[{character_id, skill_id, level, object_id?}, ...]`。
  一件ごとに `CharacterSkill` を一件足す(既にある技の熟練度を「直す」の
  ではなく、その時点の水準を新しい一件として積む)

どちらも `character_id`(と `character_skills` の `skill_id`)の実在確認を
してから書き込む。スキーマに無い欄が混ざっていたら、そこでも止める。
"""
from __future__ import annotations

from DEM.claude_interface.randomizer._base import CommitDraft
from DEM.db.schema import (
    Character, CharacterDrive, CharacterSkill, Event, EventCharacter,
    EventObject, Location, Object, Skill,
)
from DEM.db.schema_pydantic import to_dict


def _check_columns(model: type, data: dict) -> None:
    """`model` のスキーマに無い欄が混ざっていないか確かめる。"""
    columns = {column.key for column in model.__table__.columns} - {"id"}
    unknown = set(data) - columns
    if unknown:
        raise ValueError(f"{model.__name__} のスキーマに無い欄: {sorted(unknown)}")


class CommitEvent(CommitDraft):
    """出来事を一件、db へ確定して、格納後の中身を辞書で返す。

    `event` は JSON 文字列でも辞書でもよい。`id` キーは無視する
    (採番は db に任せる)。
    """

    model = Event

    def __init__(self, event: str | dict):
        self.event = event

    def execute(self, session) -> dict:
        data = self.parse(self.event)
        data.pop("id", None)
        character_ids = [int(id_) for id_ in data.pop("character_ids", None) or []]
        object_ids = [int(id_) for id_ in data.pop("object_ids", None) or []]
        drives = [dict(d) for d in data.pop("character_drives", None) or []]
        skills = [dict(s) for s in data.pop("character_skills", None) or []]

        self.check_columns(data)
        if not data.get("name"):
            raise ValueError("name は必須")
        if data.get("time") is None:
            raise ValueError("time は必須")

        self.check_exists(session, Event, data.get("parent_event_id"), "parent_event_id")
        self.check_exists(session, Location, data.get("location_id"), "location_id")
        for character_id in character_ids:
            self.check_exists(session, Character, character_id, "character_ids")
        for object_id in object_ids:
            self.check_exists(session, Object, object_id, "object_ids")

        for drive in drives:
            drive.pop("id", None)
            _check_columns(CharacterDrive, drive)
            self.check_exists(session, Character, drive.get("character_id"), "character_drives.character_id")
            if not drive.get("text"):
                raise ValueError("character_drives.text は必須")
        for skill in skills:
            skill.pop("id", None)
            _check_columns(CharacterSkill, skill)
            self.check_exists(session, Character, skill.get("character_id"), "character_skills.character_id")
            self.check_exists(session, Object, skill.get("object_id"), "character_skills.object_id")
            self.check_exists(session, Skill, skill.get("skill_id"), "character_skills.skill_id")
            if skill.get("skill_id") is None:
                raise ValueError("character_skills.skill_id は必須")

        record = Event(**data)
        record.event_characters = [
            EventCharacter(character_id=character_id) for character_id in character_ids]
        record.event_objects = [
            EventObject(object_id=object_id) for object_id in object_ids]
        session.add(record)
        for drive in drives:
            session.add(CharacterDrive(**drive))
        for skill in skills:
            session.add(CharacterSkill(**skill))
        session.commit()
        return {
            **to_dict(record),
            "character_ids": character_ids,
            "object_ids": object_ids,
            "character_drives": drives,
            "character_skills": skills,
        }
