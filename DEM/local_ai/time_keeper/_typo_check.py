#!/usr/bin/env python3
"""生成した出来事の名前・本文を、居合わせた人物・対象の正式な `name` と照らして誤字・表記ゆれが無いか確認する。"""
from __future__ import annotations

from DEM.db.schema import Character
from DEM.local_ai import ai_client

_SYSTEM_PROMPT = (
    "あなたは、生成された出来事の記録を確認する校正者です。渡す「正しい"
    "名前の一覧」(character_id を持つ)と、"
    "出来事の名前・本文を見比べ、本文中に一覧の名前と紛らわしい誤字・"
    "表記ゆれ(似ているが違う表記、文字の入れ替わり、送り仮名や括弧の"
    "崩れなど)が無いかを確認してください。見つかったら、一覧にある"
    "正式な表記に直してください。誤字が無ければ、名前も本文もそのまま"
    "返す。名前の表記以外(出来事の展開や意味、文体)は書き換えない。"
    "JSON で答えてください。キーは event_name(直した出来事の名前)、"
    "event_text(直した出来事の本文)の二つだけ。"
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "event_name": {"type": "string"},
        "event_text": {"type": "string"},
    },
    "required": ["event_name", "event_text"],
    "additionalProperties": False,
}


def check_typos(
    event_name: str, event_text: str, characters: list[Character],
) -> tuple[str, str]:
    """生成した出来事の名前・本文を、渡した人物・対象の正式名と照らして誤字・表記ゆれが無いか、もう一度ローカルAIに確認させる。"""
    known_names = [{"character_id": c.id, "name": c.name} for c in characters]
    if not known_names:
        return event_name, event_text
    prompt = (
        f"正しい名前の一覧: {known_names}\n"
        f"出来事の名前: {event_name}\n"
        f"出来事の本文: {event_text}\n"
        "誤字・表記ゆれが無いか確認し、あれば直してください。"
    )
    checked = ai_client.try_generate_json(prompt, _SCHEMA, system=_SYSTEM_PROMPT)
    return (
        checked.get("event_name") or event_name,
        checked.get("event_text") or event_text,
    )
