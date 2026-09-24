#!/usr/bin/env python3
"""作品(`Story`)の次の話(`Episode`)を Claude Code に書かせて db へ確定する。

材料は `start_story` 入口と同じ(作品の見出し・直前の話・断面・顔ぶれ)。
`local_ai` には本文を書く生成器が無いので、ここだけは claude_ai 固有。
自動生成なので `synced` は立てて確定する(`schema.py` の `Episode.synced` の注記どおり)。
"""
from __future__ import annotations

import json

from sqlalchemy import select

from DEM.ai.instructions.style import EPISODE_STYLE_INSTRUCTION
from DEM.ai.claude_code import ai_client
from DEM.ai.claude_code.interface.story import _rows
from DEM.data_access_logic.query import common_query
from DEM.db.schema import Episode, Session, StorySummary, get_env_session, summary_source_hash

# 一話ぶんの本文を書かせるので、断片の JSON より長く待つ。
EPISODE_TIMEOUT = 900.0

# 本文の代わりに概要で渡す、直前の話の本数。文体の覚え書きは一番新しい話のものを使う。
RECAP_EPISODE_LIMIT = 3
RECAP_TIMEOUT = 300.0

_SYSTEM_PROMPT = f"""\
あなたは日本語のライトノベルを書く作家です。
作品の見出し・直前の話・世界の断面・顔ぶれを渡すので、この作品の次の話を一話ぶん書いてください。
直前の話は本文の代わりに概要(summary)で渡します。概要の筋をそのまま受け継ぎ、文体の覚え書きを渡したときはそれに揃えてください。
{EPISODE_STYLE_INSTRUCTION}
種(key)を渡したときは、それを場面まで展開したものを本文にしてください。種に無い出来事を足さないでください。
JSON で答えてください。キーは title(サブタイトル。短く)と text(本文)の二つだけ。"""

_RECAP_SYSTEM_PROMPT = """\
あなたは日本語のライトノベルの担当編集者です。
話の本文を一話ぶん渡すので、次の話を書く作家へ渡す覚え書きを作ってください。
summary には、誰が何をして何がどうなったか、次の話へ引き継ぐ筋と、人物の立場・関係の変わりようを書いてください。
style には、地の文と会話の混ぜ方・一文の長さ・視点の置き方・語り口の癖を、真似できる言い方で書いてください。
どちらも本文を写さず、四〜六文にまとめてください。
JSON で答えてください。キーは summary と style の二つだけ。"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "text": {"type": "string"},
    },
    "required": ["title", "text"],
    "additionalProperties": False,
}

_RECAP_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "style": {"type": "string"},
    },
    "required": ["summary", "style"],
    "additionalProperties": False,
}


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _episode(session: Session, story_id: int, number: int) -> Episode | None:
    return session.scalars(
        select(Episode).where(Episode.story_id == story_id,
                              Episode.number == number)).first()


def _next_number(session: Session, story_id: int) -> int:
    """次に書く話数。本文の入っている最後の話の次(種だけの話は書かれていない扱い)。"""
    rows = session.scalars(
        select(Episode).where(Episode.story_id == story_id)
        .order_by(Episode.number)).all()
    written = [record.number for record in rows if (record.text or "").strip()]
    return (max(written) if written else 0) + 1


def _blocking_unsynced(session: Session, story_id: int, number: int) -> list[int]:
    """`number` より前の、本文があるのに台帳へ戻していない話。

    本文がまだ無い話(種だけ入れてある先の話)は、書きようがないので数えない。
    """
    rows = session.scalars(
        select(Episode).where(Episode.story_id == story_id,
                              Episode.number < number,
                              Episode.synced.is_(False))).all()
    return [record.number for record in rows if (record.text or "").strip()]


def _episode_recap(session: Session, story_id: int, episode: dict) -> dict:
    """一話ぶんの概要と文体の覚え書き。本文が前に作ったときのままなら `StorySummary` のものを使う。"""
    text = (episode.get("text") or "").strip()
    digest = summary_source_hash(text)
    row = session.scalars(
        select(StorySummary).where(StorySummary.episode_id == episode["id"])).first()
    if row is not None and row.source_hash == digest:
        return {"summary": row.summary, "style": row.style}

    decided = ai_client.try_generate_json(
        f"話: {_dump(episode)}\nこの話の概要と文体を覚え書きにしてください。",
        _RECAP_SCHEMA, system=_RECAP_SYSTEM_PROMPT, timeout=RECAP_TIMEOUT)
    note = {key: (decided.get(key) or "").strip() for key in ("summary", "style")}
    if not all(note.values()):
        return {key: value for key, value in note.items() if value}
    if row is None:
        row = StorySummary(story_id=story_id, episode_id=episode["id"])
        session.add(row)
    row.source_hash = digest
    row.summary = note["summary"]
    row.style = note["style"]
    session.commit()
    return note


def _recap(session: Session, story_id: int, episodes: list[dict]) -> dict:
    """直前の話を本文の代わりに概要で並べたもの(`episodes`)と、一番新しい話の文体の覚え書き(`style`)。

    概要が作れなかった話は本文のまま並べる。
    """
    rows, styles = [], []
    for episode in episodes:
        if not (episode.get("text") or "").strip():
            rows.append(episode)
            continue
        note = _episode_recap(session, story_id, episode)
        if note.get("summary"):
            rows.append({**{k: v for k, v in episode.items() if k != "text"}, "summary": note["summary"]})
        else:
            rows.append(episode)
        if note.get("style"):
            styles.append(note["style"])
    return {"episodes": rows, "style": styles[-1] if styles else ""}


def _materials(
    session: Session, story_id: int, time, *,
    number: int, episodes: int, count: int, reach: int, levels: int,
) -> dict:
    """`StartStory` と同じ材料。未同期の話があれば `stopped` を立てて材料を出さない。"""
    story = common_query.get_story(session, story_id)
    unsynced = _blocking_unsynced(session, story_id, number)
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
    result["episodes"] = _rows.episodes(session, story_id, count=episodes, before=number)
    result["cast"] = _rows.cast(session, story_id, until, count=count, levels=levels)
    result["brief"] = _rows.brief(session, story.place_id, until, reach=reach)
    return result


def write_next_episode(
    session: Session, story_id: int, time=None, *, number: int | None = None,
    episodes: int = RECAP_EPISODE_LIMIT, count: int = 5, reach: int = 60, levels: int = 1,
) -> Episode | None:
    """話を一件、db へ確定して返す。書けなければ None。

    `number` を省くと、本文の入っている最後の話の次を書く(種だけの話も対象になる)。
    その話に種(`key`)があればプロンプトへ載せ、本文と題だけを上書きする。
    """
    story_row = common_query.get_story(session, story_id)
    if number is None:
        number = _next_number(session, story_id)
    number = int(number)

    materials = _materials(session, story_id, time, number=number,
                           episodes=episodes, count=count, reach=reach, levels=levels)
    story = materials["story"]
    if materials["stopped"]:
        print(f"[claude_ai/story] {story['name']}: 未同期の話 {materials['unsynced']} が残っているので書かない")
        return None

    record = _episode(session, story_id, number)
    seed = (record.key or "").strip() if record is not None else ""
    recap = _recap(session, story_id, materials["episodes"])
    lines = [
        f"作品: {_dump(story)}",
        f"時刻: {materials['time']}",
        f"直前の話(古い順): {_dump(recap['episodes']) if recap['episodes'] else '(無し。第一話)'}",
    ]
    if recap["style"]:
        lines.append(f"直前の話の文体(これに揃える): {recap['style']}")
    lines += [
        f"顔ぶれ: {_dump(materials['cast'])}",
        f"世界の断面: {_dump(materials['brief'])}",
    ]
    if seed:
        lines.append(f"この話の種(これを場面まで展開する。種に無い出来事を足さない): {seed}")
    if record is not None and (record.viewpoint or record.place):
        lines.append(f"視点と場所: {record.viewpoint or ''} / {record.place or ''}")
    lines.append(f"この作品の第{number}話を書いてください。")

    decided = ai_client.try_generate_json(
        "\n".join(lines), _SCHEMA, system=_SYSTEM_PROMPT, timeout=EPISODE_TIMEOUT)
    text = (decided.get("text") or "").strip()
    if not text:
        print(f"[claude_ai/story] {story['name']} 第{number}話: 本文が得られなかったので見送り")
        return None
    title = (decided.get("title") or "").strip()

    if record is None:
        record = Episode(story_id=story_id, number=number, title=title,
                         text=text, letters=len(text), synced=True)
        session.add(record)
    else:
        record.title = title or record.title
        record.text = text
        record.letters = len(text)
        record.synced = True
    session.commit()
    print(f"[claude_ai/story] {story_row.name} 第{record.number}話「{record.title}」"
          f" id={record.id} {record.letters}字")
    return record


def write_story(story_id: int, episodes_to_write: int = 1, time=None,
                number: int | None = None) -> list[Episode]:
    """`episodes_to_write` 話ぶん続けて書く。途中で書けなければそこで止める。

    `number` を渡すとその話から書き始める(種だけ入れてある話を埋めるとき)。
    """
    written: list[Episode] = []
    with get_env_session() as session:
        for offset in range(episodes_to_write):
            target = None if number is None else int(number) + offset
            record = write_next_episode(session, story_id, time, number=target)
            if record is None:
                break
            written.append(record)
    print(f"[claude_ai] {ai_client.usage_summary()}")
    return written
