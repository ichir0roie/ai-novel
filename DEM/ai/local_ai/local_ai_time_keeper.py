#!/usr/bin/env python3
"""常駐ループ(`DEM/ai/time_keeper/main.py`)を、ローカル AI(Ollama)を生成に使って回す入口。"""
from __future__ import annotations

from DEM.db.schema import Session, Stamp
from DEM.ai.local_ai import ai_client
from DEM.ai.time_keeper import character_plot_progression, main


def loop_time(start_time: Stamp | None = None, max_days: int | None = None) -> Stamp:
    return main.loop_time(ai_client, start_time, max_days)


def time_process(s: Session, time: Stamp):
    return main.time_process(s, time, ai_client)


def loop_character_plots(start_time: Stamp | None = None, max_months: int | None = None) -> Stamp:
    return character_plot_progression.loop_character_plots(ai_client, start_time, max_months)


if __name__ == "__main__":
    year = int(input("year>>"))
    stamp = Stamp(
        year
    )

    loop_time(stamp)
