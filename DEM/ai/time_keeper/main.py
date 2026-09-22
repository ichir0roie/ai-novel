#!/usr/bin/env python3
"""世界の側を、時の流れの中で自動的に進める常駐ループの本体。`DEM/local_ai/` と `DEM/claude_ai/` が共用する。

`loop_time` が1日ずつ時刻を進めながら `time_process` を呼び続け、その時刻をカバーする
筋書き(`Plot`)が一件も無くなったら止まる。再開するには `CommitPlot` で筋書きを足す。
生成に使う AI は `ai`(`AIClient` の形を満たすモジュール)として受け取り、ここでは選ばない。
"""
from __future__ import annotations

import random
import traceback

from DEM.ai.time_keeper import event_progression_generator
from DEM.data_access_logic.query import common_query, world_createion_query
from DEM.db.schema import Session, Stamp, get_session
from DEM.ai.time_keeper import (
    random_character_generator,
)
from DEM.ai.time_keeper._ai import AIClient
from DEM.ai.time_keeper._format import add_days, format_time


def loop_time(
    ai: AIClient, start_time: Stamp | None = None, max_days: int | None = None,
) -> Stamp:
    """`max_days` を渡すと、その日数だけ進めて途中でも戻る
    (省けばプロットが尽きるまで進め続ける)。
    戻り値は最後に処理した時刻。
    """
    if start_time is None:
        with get_session() as s:
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
        with get_session() as s:
            active_plots = s.scalar(
                world_createion_query.active_plot_count_select(current_time))
        if not active_plots:
            print(f"[time_keepr] {format_time(current_time)} をカバーする"
                  "プロットが無い。CommitPlot で筋書きを足すまでループを止める。")
            return current_time
        try:
            with get_session() as s:
                time_process(s, current_time, ai)
        except Exception:
            # 常駐ループなので、一日ぶんの生成が失敗しても(DB の一時的な
            # 制約違反・AI の壊れた応答など)ループ全体を止めず、
            # 記録を残して次の日へ進む。
            print(f"[time_keepr] {format_time(current_time)} の処理が失敗、"
                  "この日はスキップして続行する")
            traceback.print_exc()

        next_process_day = random.randint(1, 5)
        current_time = add_days(current_time, next_process_day)
        days_done += 1


def time_process(
    s: Session, time: Stamp, ai: AIClient,
):
    random_character_generator.generate_random(s, time, ai)
    event_progression_generator.generate_random(s, time, ai)
