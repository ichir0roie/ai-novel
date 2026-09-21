#!/usr/bin/env python3
"""世界の側を、時の流れの中で自動的に進める常駐ループ。生成そのものは claude を介さない
(ローカル AI が行う)。

`loop_time` が1日ずつ時刻を進めながら `time_process` を呼び続け、その時刻をカバーする
筋書き(`Plot`)が一件も無くなったら止まる。再開するには `CommitPlot` で筋書きを足す。

`claude_main` は、このループを claude code から起動するための非対話の入口
(`IHG/workflow.md` に書いた運用タスク)。
"""
from __future__ import annotations

import random
import traceback

from DEM.db.schema import Session, Stamp, get_session
from DEM.data_access_logic.query import common_query, world_createion_query
from DEM.local_ai.time_keeper import (
    character_lifespan,
    event_progression_generator,
    random_character_generator,
    random_location_generator,
)
from DEM.local_ai.time_keeper._format import add_days, format_time


def loop_time(start_time: Stamp | None = None, max_days: int | None = None) -> Stamp:
    """`max_days` を渡すと、その日数だけ進めて途中でも戻る
    (省けばプロットが尽きるまで進め続ける、これまで通りの挙動)。
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
                time_process(s, current_time)
        except Exception:
            # 常駐ループなので、一日ぶんの生成が失敗しても(DB の一時的な
            # 制約違反・ローカルAIの壊れた応答など)ループ全体を止めず、
            # 記録を残して次の日へ進む。
            print(f"[time_keepr] {format_time(current_time)} の処理が失敗、"
                  "この日はスキップして続行する")
            traceback.print_exc()

        next_process_day = random.randint(1, 5)
        current_time = add_days(current_time, next_process_day)
        days_done += 1


def time_process(
    s: Session, time: Stamp
):
    random_character_generator.generate_random(s, time)
    event_progression_generator.generate_random(s, time)


if __name__ == "__main__":
    year = int(input("year>>"))
    stamp = Stamp(
        year
    )

    loop_time(stamp)
