#!/usr/bin/env python3
"""JSON で受け取った出来事を一件、db へ確定する、claude が呼ぶ入口。

`CreateRandomEvent` が返した辞書を claude が文脈に合わせて書き換えた
ものを受け取る想定。db に触れるのはこのモジュールだけ——
`create_random_event` 側は一切 db を見ない。

実在レコードを指す欄(`location_id` `character_ids` `parent_event_id`)は、
渡された id が db に実在するかをここで確かめてから書き込む。`character_ids`
は id のリスト(多対多。何人でも渡せる。省けば空の一覧のまま)で、
`event_character`(中間テーブル)へ一件ずつ書き込む。`name` と `time` は必須。
スキーマに無い欄が混じっていたら(`db/schema.py` の `Event` の列と
照らして)そこで止める。

出来事が人物の信念・立場を大きく動かしたときは、その変化は `Character.text`
へ文章として書き込む(`update_character` を使う)。
"""
from __future__ import annotations

from ai.claude_code import ai_client
from ai.claude_code.interface.randomizer._base import CommitDraft
from ai.time_keeper import generated_content
from db.schema import Character, Event, EventCharacter, Location, get_env_session
from db.schema_pydantic import to_dict


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

        self.check_columns(data)
        if not data.get("name"):
            raise ValueError("name は必須")
        if data.get("time") is None:
            raise ValueError("time は必須")

        self.check_exists(session, Event, data.get("parent_event_id"), "parent_event_id")
        self.check_exists(session, Location, data.get("location_id"), "location_id")
        for character_id in character_ids:
            self.check_exists(session, Character, character_id, "character_ids")

        record = Event(**data)
        record.event_characters = [
            EventCharacter(character_id=character_id) for character_id in character_ids]
        session.add(record)
        self.finalize(session, record)
        return {**to_dict(record), "character_ids": character_ids}

    def run(self) -> dict:
        result = super().run()
        with get_env_session() as session:
            generated_content.refresh(session, ai_client, session.get(Event, result["id"]))
        return result
