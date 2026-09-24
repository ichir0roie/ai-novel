#!/usr/bin/env python3
"""世界の側を、時の流れの中で自動的に進める常駐ループの本体。`ai/local_ai/` と `ai/claude_code/` が共用する。

`loop_time` が1日ずつ時刻を進めながら `time_process` を呼び続け、その時刻をカバーする
作品(`Story`)が一件も無くなったら止まる。再開するには `CommitStory` で作品を足す。
生成に使う AI は `ai`(`AIClient` の形を満たすモジュール)として受け取り、ここでは選ばない。
"""
from __future__ import annotations

import random
import traceback

from ai.time_keeper import character_event_generator, event_progression_generator, event_seed
from data_access_logic.query import common_query, world_createion_query
from db.schema import Session, Stamp, Story, get_env_session
from ai.time_keeper import (
    random_character_generator,
)
from ai.time_keeper._ai import AIClient
from ai.time_keeper._export import export_step
from ai.time_keeper._format import add_days, add_years, days_between, format_time


def loop_time(
    ai: AIClient, start_time: Stamp | None = None, max_days: int | None = None,
) -> Stamp:
    """`max_days` を渡すと、その日数だけ進めて途中でも戻る
    (省けば作品が尽きるまで進め続ける)。
    戻り値は最後に処理した時刻。
    """
    if start_time is None:
        with get_env_session() as s:
            start_time = s.scalar(
                common_query.latest_time_select()
            ) or Stamp(1)
    current_time = start_time
    days_done = 0

    while True:
        if max_days is not None and days_done >= max_days:
            print(f"[time_keepr] {format_time(current_time)} で "
                  f"{max_days} 日ぶん進めて区切る")
            return current_time
        print(f"[time_keepr] {format_time(current_time)}")
        with get_env_session() as s:
            active_stories = s.scalar(
                world_createion_query.active_story_count_select(current_time))
        if not active_stories:
            print(f"[time_keepr] {format_time(current_time)} をカバーする"
                  "作品が無い。CommitStory で作品を足すまでループを止める。")
            return current_time
        with get_env_session() as s:
            time_process(s, current_time, ai)
        # export_step(format_time(current_time))

        next_process_day = random.randint(1, 60)
        current_time = add_days(current_time, next_process_day)
        days_done += 1


def time_process(
    s: Session, time: Stamp, ai: AIClient,
):
    random_character_generator.generate_random(s, time, ai)
    event_progression_generator.generate_random(s, time, ai)


def daily_event(ai: AIClient) -> int | None:
    """サブキャラクター一人の次の出来事を一件起こす(毎日のルーチン)。起こした出来事の id を返す。
    先に、まだ抜き出していない元から出来事の種を抜き出し、たまっていれば似た種をまとめる。"""
    with get_env_session() as s:
        event_seed.refresh(s, ai)
        event_seed.consolidate(s, ai)
        record = character_event_generator.generate_next(s, ai)
        return record.id if record is not None else None


def loop_time_for_story(ai: AIClient, story_id: int, years: int = 5) -> Stamp:
    """作品 `story_id` の開始時刻(`start`)から、`years` 年ぶん `loop_time` を回す。"""
    with get_env_session() as s:
        story = s.get(Story, story_id)
        if story is None:
            raise ValueError(f"作品 id={story_id} が見つからない")
        if story.start is None:
            raise ValueError(f"作品 id={story_id} に start が無い")
        start_time = story.start
    max_days = days_between(start_time, add_years(start_time, years))
    return loop_time(ai, start_time, max_days)
