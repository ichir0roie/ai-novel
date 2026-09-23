#!/usr/bin/env python3
"""世界の側を、時の流れの中で自動的に進める常駐ループの本体。`DEM/ai/local_ai/` と `DEM/ai/claude_code/` が共用する。

`loop_time` が1日ずつ時刻を進めながら `time_process` を呼び続け、その時刻をカバーする
筋書き(`Plot`)が一件も無くなったら止まる。再開するには `CommitPlot` で筋書きを足す。
生成に使う AI は `ai`(`AIClient` の形を満たすモジュール)として受け取り、ここでは選ばない。
一歩(1日ぶん)進めるごとに `worlds/` へ書き出す(`_export.export_step`)。
"""
from __future__ import annotations

import random
import traceback

from DEM.ai.time_keeper import event_progression_generator
from DEM.data_access_logic.query import common_query, world_createion_query
from DEM.db.schema import Plot, Session, Stamp, get_env_session
from DEM.ai.time_keeper import (
    random_character_generator,
)
from DEM.ai.time_keeper._ai import AIClient
from DEM.ai.time_keeper._export import export_step
from DEM.ai.time_keeper._format import add_days, add_years, days_between, format_time


def loop_time(
    ai: AIClient, start_time: Stamp | None = None, max_days: int | None = None,
) -> Stamp:
    """`max_days` を渡すと、その日数だけ進めて途中でも戻る
    (省けばプロットが尽きるまで進め続ける)。
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
            active_plots = s.scalar(
                world_createion_query.active_plot_count_select(current_time))
        if not active_plots:
            print(f"[time_keepr] {format_time(current_time)} をカバーする"
                  "プロットが無い。CommitPlot で筋書きを足すまでループを止める。")
            return current_time
        with get_env_session() as s:
            time_process(s, current_time, ai)
        # export_step(format_time(current_time))

        next_process_day = random.randint(1, 5)
        current_time = add_days(current_time, next_process_day)
        days_done += 1


def time_process(
    s: Session, time: Stamp, ai: AIClient,
):
    random_character_generator.generate_random(s, time, ai)
    event_progression_generator.generate_random(s, time, ai)


def loop_time_for_plot(ai: AIClient, plot_id: int, years: int = 5) -> Stamp:
    """筋書き `plot_id` の開始時刻(`start`)から、`years` 年ぶん `loop_time` を回す。"""
    with get_env_session() as s:
        plot = s.get(Plot, plot_id)
        if plot is None:
            raise ValueError(f"筋書き id={plot_id} が見つからない")
        if plot.start is None:
            raise ValueError(f"筋書き id={plot_id} に start が無い")
        start_time = plot.start
    max_days = days_between(start_time, add_years(start_time, years))
    return loop_time(ai, start_time, max_days)
