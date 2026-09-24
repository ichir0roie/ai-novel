#!/usr/bin/env python3
from __future__ import annotations
import random

from db.schema import Stamp
from ai.time_keeper import constants


def is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


_DAYS_IN_400_YEARS = 146097


def _days_in_month(year: int, month: int) -> int:
    if month == 2 and is_leap_year(year):
        return 29
    return constants.MONTH_DAYS[month - 1]


def _days_before_year(year: int) -> int:
    y = year - 1
    return 365 * y + y // 4 - y // 100 + y // 400


def _to_ordinal(time: Stamp) -> int:
    days = _days_before_year(time.year)
    days += sum(_days_in_month(time.year, m) for m in range(1, time.month))
    return days + time.day


def _from_ordinal(ordinal: int, hour: int, minute: int, second: int) -> Stamp:
    year = ordinal * 400 // _DAYS_IN_400_YEARS + 1
    while _days_before_year(year) >= ordinal:
        year -= 1
    while _days_before_year(year + 1) < ordinal:
        year += 1
    day = ordinal - _days_before_year(year)
    month = 1
    while day > _days_in_month(year, month):
        day -= _days_in_month(year, month)
        month += 1
    return Stamp(year, month, day, hour, minute, second)


def add_days(time: Stamp, days: int) -> Stamp:
    return _from_ordinal(_to_ordinal(time) + days,
                         time.hour, time.minute, time.second)


def add_years(time: Stamp, years: int) -> Stamp:
    return Stamp(time.year + years, time.month, time.day,
                 time.hour, time.minute, time.second)


def days_between(start: Stamp, end: Stamp) -> int:
    return _to_ordinal(end) - _to_ordinal(start)


def format_time(time: Stamp) -> str:
    text = f"{time.year}年{time.month}月{time.day}日"
    if (time.hour, time.minute, time.second) != (0, 0, 0):
        text += f" {time.hour}時{time.minute}分{time.second}秒"
    return text


def next_month_start(time: Stamp) -> Stamp:
    if time.month == 12:
        return Stamp(time.year + 1, 1, 1)
    return Stamp(time.year, time.month + 1, 1)
