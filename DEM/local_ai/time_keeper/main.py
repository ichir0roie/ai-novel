#!/usr/bin/env python3
"""常駐ループ(`DEM/time_keeper/main.py`)を、ローカル AI(Ollama)を生成に使って回す入口。"""
from __future__ import annotations

from DEM.db.schema import Session, Stamp
from DEM.local_ai import ai_client
from DEM.time_keeper import main as _main


def loop_time(start_time: Stamp | None = None, max_days: int | None = None) -> Stamp:
    return _main.loop_time(ai_client, start_time, max_days)


def time_process(s: Session, time: Stamp):
    return _main.time_process(s, time, ai_client)


if __name__ == "__main__":
    year = int(input("year>>"))
    stamp = Stamp(
        year
    )

    loop_time(stamp)
