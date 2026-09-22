#!/usr/bin/env python3
"""作品(`Story`)の次の話(`Episode`)を Claude Code に書かせて db へ確定する。

材料は `start_story` 入口と同じ(作品の見出し・直前の話・断面・顔ぶれ)。
`local_ai` には本文を書く生成器が無いので、ここだけは claude_ai 固有。
自動生成なので `synced` は立てて確定する(`schema.py` の `Episode.synced` の注記どおり)。
"""
from __future__ import annotations

import json

from DEM.ai.instructions.principles import AVOID_NARO_TEMPLATE_INSTRUCTION
from DEM.ai.instructions.story_writing import EPISODE_WRITING_INSTRUCTION
from DEM.ai.claude_code import ai_client
from DEM.ai.claude_code.interface.story import _rows
from DEM.data_access_logic.query import common_query
from DEM.db.schema import Episode, Session, get_session

# 一話ぶんの本文を書かせるので、断片の JSON より長く待つ。
EPISODE_TIMEOUT = 900.0

_SYSTEM_PROMPT = f"""\
あなたは日本語のライトノベルを書く作家です。
作品の見出し・直前の話・世界の断面・顔ぶれを渡すので、この作品の次の話を一話ぶん書いてください。
{EPISODE_WRITING_INSTRUCTION}
{AVOID_NARO_TEMPLATE_INSTRUCTION}
JSON で答えてください。キーは title(サブタイトル。短く)と text(本文)の二つだけ。"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "text": {"type": "string"},
    },
    "required": ["title", "text"],
    "additionalProperties": False,
}


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _materials(
    session: Session, story_id: int, time, *,
    episodes: int, count: int, reach: int, levels: int,
) -> dict:
    """`StartStory` と同じ材料。未同期の話があれば `stopped` を立てて材料を出さない。"""
    story = common_query.get_story(session, story_id)
    unsynced = _rows.unsynced_episodes(session, story_id)
    result = {
        "story": _rows.story_digest(session, story),
        "unsynced": unsynced,
        "stopped": bool(unsynced),
    }
    if result["stopped"]:
        return result
    if story.place_id is None:
        raise ValueError(f"作品 {story.name} に立つ場所(place_id)が無い")
    _, until = common_query.resolve_time(session, time, story)
    result["time"] = str(until)
    result["episodes"] = _rows.episodes(session, story_id, count=episodes)
    result["cast"] = _rows.cast(session, story_id, until, count=count, levels=levels)
    result["brief"] = _rows.brief(session, story.place_id, until, reach=reach)
    return result


def write_next_episode(
    session: Session, story_id: int, time=None, *,
    episodes: int = 10, count: int = 5, reach: int = 60, levels: int = 1,
) -> Episode | None:
    """次の話を一件、db へ確定して返す。未同期の話が残っていれば書かずに None。"""
    materials = _materials(
        session, story_id, time, episodes=episodes, count=count, reach=reach, levels=levels)
    story = materials["story"]
    if materials["stopped"]:
        print(f"[claude_ai/story] {story['name']}: 未同期の話 {materials['unsynced']} が残っているので書かない")
        return None

    number = (story["last_episode"] or 0) + 1
    prompt = (
        f"作品: {_dump(story)}\n"
        f"時刻: {materials['time']}\n"
        f"直前の話(古い順): {_dump(materials['episodes']) if materials['episodes'] else '(無し。第一話)'}\n"
        f"顔ぶれ: {_dump(materials['cast'])}\n"
        f"世界の断面: {_dump(materials['brief'])}\n"
        f"この作品の第{number}話を書いてください。"
    )
    decided = ai_client.try_generate_json(
        prompt, _SCHEMA, system=_SYSTEM_PROMPT, timeout=EPISODE_TIMEOUT)
    text = (decided.get("text") or "").strip()
    if not text:
        print(f"[claude_ai/story] {story['name']} 第{number}話: 本文が得られなかったので見送り")
        return None

    record = Episode(
        story_id=story_id, number=number,
        title=(decided.get("title") or "").strip(),
        text=text, letters=len(text), synced=True,
    )
    session.add(record)
    session.commit()
    print(f"[claude_ai/story] {story['name']} 第{record.number}話「{record.title}」"
          f" id={record.id} {record.letters}字")
    return record


def write_story(story_id: int, episodes_to_write: int = 1, time=None) -> list[Episode]:
    """`episodes_to_write` 話ぶん続けて書く。途中で書けなければそこで止める。"""
    written: list[Episode] = []
    with get_session() as session:
        for _ in range(episodes_to_write):
            record = write_next_episode(session, story_id, time)
            if record is None:
                break
            written.append(record)
    print(f"[claude_ai] {ai_client.usage_summary()}")
    return written
