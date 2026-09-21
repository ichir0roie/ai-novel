#!/usr/bin/env python3
"""世界の側を、時の流れの中で自動的に進める常駐ループ。claude を介さない。

`loop_time` が1日ずつ時刻を進めながら `time_process` を呼び続け、その時刻をカバーする
筋書き(`Plot`)が一件も無くなったら止まる。再開するには `CommitPlot` で筋書きを足す。
"""
from __future__ import annotations

import traceback

from DEM.db.schema import Session, Stamp, get_session
from DEM.data_access_logic.query import common_query, world_createion_query
from DEM.local_ai.time_keeper import (
    character_lifespan,
    event_progression_generator,
    random_character_generator,
    random_location_generator,
    random_object_generator,
)
from DEM.local_ai.time_keeper._format import format_time, next_day


def loop_time(start_time: Stamp | None = None):
    if start_time is None:
        with get_session() as s:
            start_time = s.scalar(
                common_query.latest_time_select()
            ) or Stamp(1)
    current_time = start_time

    while True:
        print(f"[time_keepr] {format_time(current_time)}")
        with get_session() as s:
            active_plots = s.scalar(
                world_createion_query.active_plot_count_select(current_time))
        if not active_plots:
            print(f"[time_keepr] {format_time(current_time)} をカバーする"
                  "プロットが無い。CommitPlot で筋書きを足すまでループを止める。")
            return
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

        current_time = next_day(current_time)


def time_process(
    s: Session, time: Stamp
):
    random_location_generator.generate_random(s, time)

    # フラグを立てた場所へ、まだ誰も居なければまとめて人物を生む(月初)。
    # 月一件だけの generate_random より先に呼び、同じ月内に両方当たっても
    # 二重に生まれない(seed 側は「まだ誰も居ない」場所だけを対象にする)。
    random_character_generator.seed_initial_characters(s, time)
    random_character_generator.generate_random(s, time)

    # 個体(国・組織など)は、人物が居る場所にだけ生む。人物を生む側より
    # 後に呼び、その月に生まれたばかりの人物も候補の材料に入るようにする。
    random_object_generator.generate_random(s, time)

    character_lifespan.generate_random(s, time)
    event_progression_generator.generate_random(s, time)


if __name__ == "__main__":
    year = int(input("year>>"))
    stamp = Stamp(
        year
    )

    loop_time(stamp)
