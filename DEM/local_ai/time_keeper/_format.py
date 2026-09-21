#!/usr/bin/env python3
"""`time_keepr` のログに出す時刻を、人が読みやすい形にする。"""
from __future__ import annotations
import random

from DEM.db.schema import Stamp

_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def next_day(time: Stamp) -> Stamp:
    """時刻を1日ぶん進める。"""
    year, month, day = time.year, time.month, time.day
    days_in_month = _MONTH_DAYS[month - 1]
    if month == 2 and is_leap_year(year):
        days_in_month = 29

    day += random.randint(1, 60)
    if day > days_in_month:
        day = 1
        month += 1
        if month > 12:
            month = 1
            year += 1

    return Stamp(year, month, day, time.hour, time.minute, time.second)


def add_days(time: Stamp, days: int) -> Stamp:
    """時刻を `days` 日ぶん進める。`next_day` を `days` 回繰り返すだけの素朴な実装。"""
    result = time
    for _ in range(max(days, 0)):
        result = next_day(result)
    return result


def format_time(time: Stamp) -> str:
    """**`1234年5月6日`。** 時刻が0時0分0秒でなければ、そこも続けて出す。"""
    text = f"{time.year}年{time.month}月{time.day}日"
    if (time.hour, time.minute, time.second) != (0, 0, 0):
        text += f" {time.hour}時{time.minute}分{time.second}秒"
    return text
