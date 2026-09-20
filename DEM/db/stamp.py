#!/usr/bin/env python3
"""作中の時刻。**python の `datetime` は 9999 年までしか持てないので使わない。**

作中の暦は西暦の続きで、万の位に乗る年も出る(`43600712`、`999990101000000`)。
`datetime` はそこで `year is out of range` と言って止まるため、
ここでは年・月・日・時・分・秒をそのまま持つ小さな値として扱う。

```
Stamp.parse("4360")            → 4360 年 1 月 1 日 0 時
Stamp.parse("43600712")        → 4360 年 7 月 12 日
Stamp.parse("99999")           → 99999 年 1 月 1 日(奇数桁なら年は 5 桁)
Stamp.parse("99999-01-01")     → 同じ
Stamp.parse("999990101000000") → 同じ(15 桁以上なら、後ろ 10 桁を落とした残りが年)
```

**台帳には整数として入れる**(`年*10^10 + 月*10^8 + … + 秒`)。
桁を並べただけなので、大小がそのまま時の前後になる。
"""
from __future__ import annotations

import datetime as _datetime
import re
from functools import total_ordering

_DIGITS = re.compile(r"\A\d+\Z")

# ファイル名の頭。`4340_1_1` と `4340_1_1_093000`
_STEM = re.compile(r"\A(\d+)_(\d{1,2})_(\d{1,2})(?:_(\d{6}))?\Z")

# 年の下に付く五つの欄。桁数と、書かれなかったときの値
_PARTS = (("month", 2, 1), ("day", 2, 1),
          ("hour", 2, 0), ("minute", 2, 0), ("second", 2, 0))

# 年より下の桁の合計。10 桁(mmddhhmmss)
_UNDER = sum(width for _, width, _ in _PARTS)

# 月ごとの日数(平年)。うるう年は2月だけ+1する。
_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_DAYS_BEFORE_MONTH = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


class StampError(ValueError):
    """時刻として読めなかった。"""


@total_ordering
class Stamp:
    """作中の一点。**年に上限はない。**"""

    __slots__ = ("year", "month", "day", "hour", "minute", "second")

    def __init__(self, year, month=1, day=1, hour=0, minute=0, second=0):
        self.year = int(year)
        self.month = int(month)
        self.day = int(day)
        self.hour = int(hour)
        self.minute = int(minute)
        self.second = int(second)
        if not 1 <= self.month <= 12:
            raise StampError(f"月が 1〜12 でない: {self.month}")
        if not 1 <= self.day <= 31:
            raise StampError(f"日が 1〜31 でない: {self.day}")
        if not (0 <= self.hour < 24 and 0 <= self.minute < 60
                and 0 <= self.second < 60):
            raise StampError(f"時刻の桁が範囲の外: {self}")

    # --- 作る -----------------------------------------------------------

    @classmethod
    def parse(cls, value) -> "Stamp | None":
        """`4360/7/12 09:30:00` も `4360/7/12` も `4360` も受け取る。

        **年は西暦の続き。** 粒度は混ぜてよい。書かれなかった桁は
        1 月 1 日 0 時で埋める。数字だけなら年とみなす。
        """
        if value is None or value == "":
            return None
        if isinstance(value, Stamp):
            return value
        if isinstance(value, _datetime.datetime):
            return cls(value.year, value.month, value.day,
                       value.hour, value.minute, value.second)
        if isinstance(value, _datetime.date):
            return cls(value.year, value.month, value.day)

        text = str(value).strip()
        if not text:
            return None

        if _DIGITS.match(text):
            if len(text) > 6:
                raise StampError(
                    f"年として長すぎる: {text}。"
                    f"日付まで書くなら y/mm/dd hh:mm:ss の形にする")
            return cls(int(text))

        parts = [p for p in re.split(r"[-/ :T]", text) if p != ""]
        if not parts or not all(p.isdigit() for p in parts):
            raise StampError(f"時刻として読めない: {value!r}")
        nums = [int(p) for p in parts[:6]]
        return cls(*nums)

    @classmethod
    def from_stem(cls, stem: str) -> "Stamp | None":
        """ファイル名の頭(`4340_01_01` / `4340_01_01_093000`)を読む。"""
        m = _STEM.match(stem)
        if not m:
            return None
        year, month, day, clock = m.groups()
        hour, minute, second = (0, 0, 0)
        if clock:
            hour, minute, second = (int(clock[i:i + 2]) for i in (0, 2, 4))
        return cls(int(year), int(month), int(day), hour, minute, second)

    @classmethod
    def from_int(cls, value) -> "Stamp | None":
        """台帳に入っている整数から戻す。"""
        if value is None:
            return None
        value = int(value)
        rest, second = divmod(value, 100)
        rest, minute = divmod(rest, 100)
        rest, hour = divmod(rest, 100)
        rest, day = divmod(rest, 100)
        year, month = divmod(rest, 100)
        return cls(year, month, day, hour, minute, second)

    # --- 出す -----------------------------------------------------------

    def to_int(self) -> int:
        """桁を並べた整数。**そのまま並べ替えに使える。**"""
        return (((((self.year * 100 + self.month) * 100 + self.day) * 100
                  + self.hour) * 100 + self.minute) * 100 + self.second)

    def to_seconds(self) -> int:
        """**プロレプティック・グレゴリオ暦での、相対的な秒数。**

        絶対的な暦の起点は決めていない(西暦0年をそのまま起点にしただけ)ので、
        単独の値には意味がなく、二点の差分(間に何秒あるか)を見るのにだけ使う
        (`LocationResource` の残量のような、時の幅に対する線形補間)。
        """
        days_before_year = (365 * self.year + self.year // 4
                            - self.year // 100 + self.year // 400)
        day_of_year = _DAYS_BEFORE_MONTH[self.month - 1] + self.day
        if self.month > 2 and _is_leap_year(self.year):
            day_of_year += 1
        days = days_before_year + day_of_year
        return ((days * 24 + self.hour) * 60 + self.minute) * 60 + self.second

    def stem(self) -> str:
        """ファイル名の頭。**0 時ちょうどなら時刻を書かない。**

        `4340_01_01` / `4340_01_01_093000`
        """
        head = f"{self.year}_{self.month:02d}_{self.day:02d}"
        if (self.hour, self.minute, self.second) == (0, 0, 0):
            return head
        return f"{head}_{self.hour:02d}{self.minute:02d}{self.second:02d}"

    def __str__(self) -> str:
        """**`y/mm/dd hh:mm:ss`。** 中でも外でもこの書き方で通す。"""
        return (f"{self.year}/{self.month:02d}/{self.day:02d} "
                f"{self.hour:02d}:{self.minute:02d}:{self.second:02d}")

    def __repr__(self) -> str:
        return f"Stamp({self})"

    # --- 比べる ---------------------------------------------------------

    def __eq__(self, other) -> bool:
        return isinstance(other, Stamp) and self.to_int() == other.to_int()

    def __lt__(self, other) -> bool:
        if not isinstance(other, Stamp):
            return NotImplemented
        return self.to_int() < other.to_int()

    def __hash__(self) -> int:
        return hash(self.to_int())
