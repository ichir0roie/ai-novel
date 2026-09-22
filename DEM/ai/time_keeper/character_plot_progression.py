#!/usr/bin/env python3
"""既にいる人物とその筋書き(`CharacterPlot`)だけを材料に、出来事を進め続ける常駐ループ。

`loop_time` と違い、人物・場所は増やさず、場所の筋書き(`Plot`)も要らない。
月に一度、有効な筋書きを持つ人物が居る場所ごとに出来事を一件起こし、
その時刻をカバーする人物の筋書きが一件も無くなったら止まる。
"""
from __future__ import annotations

import random

from DEM.ai.time_keeper import event_progression_generator
from DEM.ai.time_keeper._ai import AIClient
from DEM.ai.time_keeper._format import format_time, next_month_start
from DEM.data_access_logic.query import (
    common_query, story_createion_query, world_createion_query,
)
from DEM.db.schema import Character, Event, Session, Stamp, get_session


def _group_plot_holders_by_place(
    session: Session, time: Stamp,
) -> dict[int, list[Character]]:
    """`_group_by_place` の結果のうち、有効な筋書きを持つ人物が一人でも居る場所だけ残す。
    同じ場所に居る筋書きの無い人物・対象も、出来事の相手として一緒に渡す。"""
    grouped = event_progression_generator._group_by_place(session, time)
    return {
        place_id: characters
        for place_id, characters in grouped.items()
        if any(story_createion_query.load_character_plot(session, c.id, time)
               for c in characters)
    }


def progress(session: Session, time: Stamp, ai: AIClient) -> list[Event]:
    """有効な筋書きを持つ人物が居る場所それぞれで、出来事を一件進める。"""
    rng = random.Random(random.randrange(10 ** 9))
    created: list[Event] = []

    grouped = _group_plot_holders_by_place(session, time)
    total_places = len(grouped)
    if not total_places:
        print(f"[time_keepr/character_plot] {format_time(time)}: "
              "筋書きを持つ人物が居る場所が無い(全員が進行中の出来事の中か、場所が無効)")
    for i, (place_id, characters) in enumerate(grouped.items(), start=1):
        print(f"[time_keepr/character_plot] 場所 {i}/{total_places} id={place_id}: "
              f"人物・対象{len(characters)}件")
        event = event_progression_generator._progress_place(
            session, place_id, characters, time, rng, ai)
        if event is not None:
            created.append(event)
    return created


def loop_character_plots(
    ai: AIClient, start_time: Stamp | None = None, max_months: int | None = None,
) -> Stamp:
    """`start_time` を省くと、db の最新の出来事の翌月1日から始める。
    `max_months` を渡すと、その月数だけ進めて途中でも戻る。戻り値は最後に処理した時刻。
    """
    if start_time is None:
        with get_session() as s:
            latest = s.scalar(common_query.latest_time_select())
        start_time = next_month_start(latest) if latest else Stamp(1)
    current_time = start_time
    months_done = 0

    while True:
        if max_months is not None and months_done >= max_months:
            print(f"[time_keepr/character_plot] {format_time(current_time)} で "
                  f"{max_months} か月ぶん進めて区切る")
            return current_time
        print(f"[time_keepr/character_plot] {format_time(current_time)}")
        with get_session() as s:
            active_plots = s.scalar(
                world_createion_query.active_character_plot_count_select(current_time))
        if not active_plots:
            print(f"[time_keepr/character_plot] {format_time(current_time)} をカバーする"
                  "人物の筋書きが無い。CommitCharacterPlot で筋書きを足すまでループを止める。")
            return current_time
        with get_session() as s:
            progress(s, current_time, ai)

        current_time = next_month_start(current_time)
        months_done += 1
