#!/usr/bin/env python3
"""作中の時刻。**python の `datetime` は 9999 年までしか持てないので使わない。**

作中の暦は西暦の続きで、万の位に乗る年も出る（`43600712`、`999990101000000`）。
`datetime` はそこで `year is out of range` と言って止まるため、
ここでは年・月・日・時・分・秒をそのまま持つ小さな値として扱う。

```
Stamp.parse("4360")            → 4360 年 1 月 1 日 0 時
Stamp.parse("43600712")        → 4360 年 7 月 12 日
Stamp.parse("99999")           → 99999 年 1 月 1 日（奇数桁なら年は 5 桁）
Stamp.parse("99999-01-01")     → 同じ
Stamp.parse("999990101000000") → 同じ（15 桁以上なら、後ろ 10 桁を落とした残りが年）
```

**台帳には整数として入れる**（`年*10^10 + 月*10^8 + … + 秒`）。
桁を並べただけなので、大小がそのまま時の前後になる。
"""
from __future__ import annotations

import datetime as _datetime
import re
from functools import total_ordering

_COMPACT = re.compile(r"\A\d{4,}\Z")

# 年の下に付く五つの欄。桁数と、書かれなかったときの値
_PARTS = (("month", 2, 1), ("day", 2, 1),
          ("hour", 2, 0), ("minute", 2, 0), ("second", 2, 0))

# 年より下の桁の合計。10 桁（mmddhhmmss）
_UNDER = sum(width for _, width, _ in _PARTS)


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
        """`43600712` も `4360-07-12` も `4360` も受け取る。

        **年は西暦の続き。** 粒度は混ぜてよい。書かれなかった桁は頭の値で埋める。
        14 桁を越える並びは、後ろ 10 桁が `mmddhhmmss`、頭の余りが年。
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

        if _COMPACT.match(text):
            return cls._from_digits(text)

        parts = [p for p in re.split(r"[-/ :T]", text) if p != ""]
        if not parts or not all(p.isdigit() for p in parts):
            raise StampError(f"時刻として読めない: {value!r}")
        nums = [int(p) for p in parts[:6]]
        return cls(*nums)

    @classmethod
    def _from_digits(cls, digits: str) -> "Stamp":
        """`4360` `43600712` `99999` `999990101000000` を割る。

        年より下は必ず二桁ずつ並ぶ。**だから桁数だけで年の長さが決まる。**

        | 桁数 | 年 | 例 |
        | --- | --- | --- |
        | 14 まで・偶数 | 頭の 4 桁 | `4360` `43600712` |
        | 14 まで・奇数 | 頭の 5 桁 | `99999` `9999901` |
        | 15 以上 | 後ろ 10 桁を落とした残り | `999990101000000`（5 桁）|
        """
        head = len(digits) - _UNDER if len(digits) > 14 else 4 + len(digits) % 2
        year, rest = digits[:head], digits[head:]
        values = []
        for _, width, blank in _PARTS:
            values.append(int(rest[:width]) if len(rest) >= width else blank)
            rest = rest[width:]
        if rest:
            raise StampError(f"時刻の桁が半端: {digits}")
        return cls(int(year), *values)

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

    def compact(self) -> str:
        """ファイル名に使う並び。年が五桁以上なら、その分だけ長くなる。"""
        return (f"{self.year:04d}{self.month:02d}{self.day:02d}"
                f"{self.hour:02d}{self.minute:02d}{self.second:02d}")

    def __str__(self) -> str:
        return (f"{self.year:04d}-{self.month:02d}-{self.day:02d} "
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
