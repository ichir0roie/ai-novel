#!/usr/bin/env python3
"""常駐ループ(`DEM/ai/time_keeper/main.py`)を、Claude Code(`claude -p`)を生成に使って回す入口。

`claude_main` は、このループを claude code から起動するための非対話の入口。
"""
from __future__ import annotations

from DEM.ai.claude_code import ai_client
from DEM.db.schema import Session, Stamp
from DEM.ai.time_keeper import character_plot_progression, main as _main


def loop_time(start_time: Stamp | None = None, max_days: int | None = None) -> Stamp:
    """終わりに Claude Code の呼び出し回数とトークンを出す。"""
    try:
        return _main.loop_time(ai_client, start_time, max_days)
    finally:
        print(f"[claude_ai] {ai_client.usage_summary()}")


def time_process(s: Session, time: Stamp):
    return _main.time_process(s, time, ai_client)


def claude_main(year: int | None = None, max_days: int | None = None) -> Stamp:
    """`year` を省くと db の最新の時刻から続ける。`max_days` を渡すとその日数で区切る。"""
    return loop_time(Stamp(year) if year is not None else None, max_days)


def loop_time_for_plot(plot_id: int, years: int = 5) -> Stamp:
    """終わりに Claude Code の呼び出し回数とトークンを出す。"""
    try:
        return _main.loop_time_for_plot(ai_client, plot_id, years)
    finally:
        print(f"[claude_ai] {ai_client.usage_summary()}")


def claude_plot_years_main(plot_id: int, years: int = 5) -> Stamp:
    """筋書き `plot_id` の開始時刻から、`years` 年ぶん進める(既定 5 年)。"""
    return loop_time_for_plot(plot_id, years)


def loop_character_plots(start_time: Stamp | None = None, max_months: int | None = None) -> Stamp:
    """既にいる人物とその筋書きだけで出来事を進め続ける。終わりに呼び出し回数とトークンを出す。"""
    try:
        return character_plot_progression.loop_character_plots(ai_client, start_time, max_months)
    finally:
        print(f"[claude_ai] {ai_client.usage_summary()}")


def claude_character_plots_main(year: int | None = None, max_months: int | None = None) -> Stamp:
    """`year` を省くと db の最新の出来事の翌月から続ける。`max_months` を渡すとその月数で区切る。"""
    return loop_character_plots(Stamp(year) if year is not None else None, max_months)


if __name__ == "__main__":
    year = int(input("year>>"))
    loop_time(Stamp(year))
