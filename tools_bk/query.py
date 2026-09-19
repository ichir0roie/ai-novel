#!/usr/bin/env python3
"""db への問い合わせと書き換えを、**関数の形で**そろえたところ。

**呼ぶ側が SQL を組み立てない。** 引く条件は「時刻」と「レコードの id」
だけで表す。足りない引き方が出てきたら、ここに関数を足す
（`novel.py` に SQL を渡す入口はもう無い）。

```
events_at(engine, "4354/09/28")   その時（年でも日でも）の出来事と行動
events_of(engine, "<id>")         その id に掛かる出来事と行動
record(engine, "<id>")            id 一件の行を、どの表からでも引く
set_text(engine, "<id>", "…")     その id の本文（text 欄）を入れ替える
```

時刻の粒度は書いた通りに効く。`4354` なら その年ぜんぶ、`4354/09/28`
なら その日ぜんぶ、`4354/09/28 17:00:00` ならその一点だけ。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import reader  # noqa: E402
import schema  # noqa: E402
import stamp  # noqa: E402

# 出来事が「誰の・どこの・どれに掛かる」を持つ欄
EVENT_REFS = ("place_id", "character_id", "object_id", "parent_event_id")


# ---------------------------------------------------------------- 時刻の幅

def span(when) -> tuple[stamp.Stamp, stamp.Stamp]:
    """時刻の指定を、**そこに収まる幅**（始め, 終わり）へ開く。

    書いた粒度がそのまま幅になる。`4354` はその年、`4354/09/28` はその日、
    `4354/09/28 17:00:00` はその一点。
    """
    import re

    text = str(when).strip()
    at = stamp.Stamp.parse(text)
    if at is None:
        raise stamp.StampError("時刻が空")
    # 書かれた欄の数。数字だけなら年一つ
    depth = 1 if text.isdigit() else \
        len([p for p in re.split(r"[-/ :T]", text) if p])
    parts = [at.year, at.month, at.day, at.hour, at.minute, at.second]
    largest = [None, 12, 31, 23, 59, 59]
    for i in range(min(depth, 6), 6):
        parts[i] = largest[i]
    return at, stamp.Stamp(*parts)


# ---------------------------------------------------------------- 引く

def _rows(engine, model, where, order):
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        rows = session.query(model).filter(where).order_by(*order).all()
        session.expunge_all()
        return rows


def events_at(engine, when) -> list:
    """**その時の出来事と行動を、ぜんぶ返す。** 引数は時刻だけ。

    場所側の出来事（`…/events/…`）も、人物・個体側の行動も同じ表に入って
    いるので、まとめて時の順に返る。
    """
    since, until = span(when)
    return _rows(engine, schema.Event,
                 schema.Event.time.between(since, until),
                 (schema.Event.time, schema.Event.id))


def events_of(engine, record_id: str) -> list:
    """**その id に掛かる出来事と行動を返す。** 引数はレコードの id だけ。

    場所の id ならそこで起きたもの、人物・個体の id ならその者の行動、
    出来事の id ならそれにぶら下がる行動が返る。
    """
    from sqlalchemy import or_

    where = or_(*[getattr(schema.Event, c) == record_id for c in EVENT_REFS])
    return _rows(engine, schema.Event, where,
                 (schema.Event.time, schema.Event.id))


def record(engine, record_id: str):
    """**id 一件を、どの表からでも引く。** 戻すのは `(表の名前, 行)`。

    見つからなければ `LookupError`。
    """
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        for table, model in reader.MODELS.items():
            row = session.get(model, record_id)
            if row is not None:
                session.expunge_all()
                return table, row
    raise LookupError(f"「{record_id}」という id の行が db に無い")


# ---------------------------------------------------------------- 書き換える

def set_text(engine, record_id: str, text: str) -> str:
    """**その id の本文（`text` 欄）を入れ替える。** 戻り値は id。

    データの欄（`場所` `時期` のような指し先）はここでは触らない。
    入れ替えたら `save` でマークダウンへ書き出す。
    """
    from sqlalchemy.orm import Session

    table, _ = record(engine, record_id)
    model = reader.MODELS[table]
    if not hasattr(model, "text"):
        raise LookupError(f"「{record_id}」（{reader.LABEL[table]}）は"
                          "本文を持たない")
    if not text.endswith("\n"):
        text += "\n"
    with Session(engine) as session:
        row = session.get(model, record_id)
        row.text = text
        session.commit()
    return record_id


# ---------------------------------------------------------------- 並べる

def show_events(rows: list, title: str) -> str:
    """出来事の行を、読める形に並べる。"""
    out = [f"# {title}", ""]
    if not rows:
        out.append("（なし）")
    for row in rows:
        at = row.time
        actor = row.character_id or row.object_id
        out.append(f"- {at} {row.name}" + (f"　[{row.kind}]" if row.kind else ""))
        if actor:
            out.append(f"  行動: {actor}")
        if row.place_id:
            out.append(f"  場所: {row.place_id}")
        if row.parent_event_id:
            out.append(f"  掛かり先: {row.parent_event_id}")
        out.append(f"  id: {row.id}")
        body = " ".join((row.text or "").split())
        if body:
            out.append(f"  {body[:200]}")
    return "\n".join(out)


def show_record(table: str, row) -> str:
    """一件の行を、データと本文に分けて並べる。"""
    out = [f"# {reader.LABEL[table]} / {getattr(row, 'name', row.id)}", ""]
    for key, column in reader.FIELDS[table].items():
        if key == "名":
            continue
        value = getattr(row, column, None)
        if value in (None, ""):
            continue
        out.append(f"{key}: {value}")
    out += [f"id: {row.id}", "", (getattr(row, "text", "") or "").strip()]
    return "\n".join(out)
