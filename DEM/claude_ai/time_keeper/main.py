#!/usr/bin/env python3
"""`DEM/local_ai/time_keeper/main.py` と同じ常駐ループを、生成だけ Claude Code(`claude -p`)で行う入口。

生成器(人物・出来事とその中の場所の改廃)は `DEM/local_ai/time_keeper/` のものを
そのまま使い、AI の呼び先だけを `DEM_AI_BACKEND=claude` で `DEM/claude_ai/ai_client.py` へ切り替える。
確率・プロンプト・db への書き方は local_ai と一切変わらない。

`claude_main` は、このループを claude code から起動するための非対話の入口。
"""
from __future__ import annotations

import os

from DEM.claude_ai import ai_client
from DEM.db.schema import Stamp
from DEM.local_ai.time_keeper import main as local_main


def use_claude() -> None:
    """このプロセスの生成を Claude Code へ向ける。"""
    os.environ["DEM_AI_BACKEND"] = "claude"


def loop_time(start_time: Stamp | None = None, max_days: int | None = None) -> Stamp:
    """`local_main.loop_time` と同じ。終わりに Claude Code の呼び出し回数とトークンを出す。"""
    use_claude()
    try:
        return local_main.loop_time(start_time, max_days)
    finally:
        print(f"[claude_ai] {ai_client.usage_summary()}")


def claude_main(year: int | None = None, max_days: int | None = None) -> Stamp:
    """`year` を省くと db の最新の時刻から続ける。`max_days` を渡すとその日数で区切る。"""
    return loop_time(Stamp(year) if year is not None else None, max_days)


if __name__ == "__main__":
    year = int(input("year>>"))
    loop_time(Stamp(year))
