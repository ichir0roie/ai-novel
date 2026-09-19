#!/usr/bin/env python3
"""台帳ツールの入口。`novels/` のマークダウンを読んで、組む・検める・断面を出す。

```
python3 tools/novel.py check                 不備を探す。あればコード 1 で止まる
python3 tools/novel.py start --story めぐる旅路は枯れゆく世界と
                                             **作業開始時。** load して、企画・プロット・
                                             直前の話・断面・顔ぶれを一度に出す
python3 tools/novel.py load                  md を db へ読み込むだけ
python3 tools/novel.py save                  **作業終了時。** db を md へ書き出す
python3 tools/novel.py stories --work めぐる旅路は枯れゆく世界と
python3 tools/novel.py read <作品名>/1
python3 tools/novel.py write <作品名>/3 --file 下書き.md
python3 tools/novel.py brief --place ムシュヴァン --time 4360
python3 tools/novel.py cast --story めぐる旅路は枯れゆく世界と
python3 tools/novel.py scene --place フリステ --time 4360
python3 tools/novel.py sync <作品名>/<話数>   モード 3 を通したあと、同期フラグを立てる
python3 tools/novel.py list --kind 語 --world SFファンタジー
python3 tools/novel.py show 采配
python3 tools/novel.py template --kind 人物
python3 tools/novel.py index --world SFファンタジー
python3 tools/novel.py episodes --story めぐる旅路は枯れゆく世界と --before 11
python3 tools/novel.py events --time 4354/09/28
python3 tools/novel.py events --of characters/フリステ/オリオ
python3 tools/novel.py show-id <レコードの id>
python3 tools/novel.py text <レコードの id> --file 本文.md
python3 tools/novel.py batch --file 引く.txt  引くものが何件もあるとき、一度の読み込みで
```

**`novels/` のマークダウンは直に開かない。** 読むのも書くのも、この入口を通す。
形は `tools/schema.py` が一か所で決めている。読み方は `tools/reader.py`。
"""
from __future__ import annotations

import argparse
import decimal
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import query  # noqa: E402
import reader  # noqa: E402
import schema  # noqa: E402
import stamp  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVELS = os.path.join(REPO, "novels")
DB = os.path.join(NOVELS, "novel.db")

# 日本語の呼び名 → テーブル名
KINDS = {v: k for k, v in reader.LABEL.items()}

# 種別の後ろに `/` で付ける注記。`core/chronicle.md`
HIDDEN = "/裏"        # 住人が知らない。既定の断面では伏せる
RETIRED = ("/死語", "/候補", "/設定側")


# ---------------------------------------------------------------- 検める

REQUIRED = {
    "place": ("name",),
    "event": ("name", "time"),
    "kind": ("name", "kind"),
    "object": ("name", "kind_id"),
    "object_place": ("object_id", "place_id"),
    "character": ("name", "read", "born_place_id"),
    "character_place": ("character_id", "place_id"),
    "term": ("name",),
    "story": ("name",),
    "episode": ("story_id", "number"),
}

# 指し先の対応は `reader.REFS` が持っている。ここで足すのは、
# 読み込みのときに構造から埋まる持ち主の欄だけ
OWNER_REFS = {
    "object_place": {"object_id": "object"},
    "character_place": {"character_id": "character"},
}

REFS = {table: {**reader.REFS.get(table, {}), **OWNER_REFS.get(table, {})}
        for table in reader.MODELS}


def inspect(lib: reader.Library) -> list[str]:
    """読めたレコードの不備を並べる。**空で返るまで次の話へ行かない。**"""
    errors = list(lib.problems)
    ids: dict[str, dict[str, str]] = {t: {} for t in reader.MODELS}

    for rec in lib.records:
        where = os.path.relpath(rec.path, REPO)
        if not rec.id:
            errors.append(f"{where}: id がない")
            continue
        seen = ids[rec.table]
        if rec.id in seen:
            errors.append(f"{where}: id「{rec.id}」が {seen[rec.id]} と重なっている")
        seen[rec.id] = where
        for column in REQUIRED[rec.table]:
            if not rec.values.get(column):
                errors.append(f"{where}: {column} が空")

    for rec in lib.records:
        where = os.path.relpath(rec.path, REPO)
        for column, table in REFS[rec.table].items():
            value = rec.values.get(column)
            if value and value not in ids[table]:
                errors.append(
                    f"{where}: {column} の指す「{value}」が"
                    f"{reader.LABEL[table]}に無い")
    return errors


# ---------------------------------------------------------------- 組む

def build(lib: reader.Library, path: str = DB):
    """読めたレコードを SQLite へ流し込む。**何度でも組み直せる。**"""
    from sqlalchemy.orm import Session

    engine = schema.create_db(path)
    order = ["place", "kind", "object", "character", "event",
             "object_place", "character_place", "term",
             "story", "episode"]
    with Session(engine) as session:
        for table in order:
            for rec in lib.of(table):
                session.add(rec.instance())
            session.flush()
        session.commit()
    return engine


# ---------------------------------------------------------------- 断面

def _year(when) -> str:
    return "" if when is None else str(when.year)


def _span(rec) -> str:
    start, end = rec.values.get("start"), rec.values.get("end")
    if start and end:
        return f"{_year(start)}〜{_year(end)}"
    if start:
        return f"{_year(start)}〜"
    return f"〜{_year(end)}" if end else ""


def _actor_of(rec):
    """出来事が誰の行動かを返す。`("character", id)` / `("object", id)`。

    どちらも空なら `None`（誰の行動でもない、ただ起きたこと）。
    **行動は出来事の一種。** 別表は持たない（tools/schema.py）。
    """
    for table, column in (("character", "character_id"),
                          ("object", "object_id")):
        owner = rec.values.get(column) if hasattr(rec, "values") else None
        if owner:
            return table, owner
    return None


def _lineage(place_id: str, places: dict) -> list[str]:
    """その場所から根まで、親をたどった連なり。"""
    chain, seen = [], set()
    while place_id and place_id in places and place_id not in seen:
        seen.add(place_id)
        chain.append(place_id)
        place_id = places[place_id].values.get("parent_id")
    return chain


def _descendants(place_id: str, places: dict) -> set[str]:
    inside = {place_id}
    grew = True
    while grew:
        grew = False
        for pid, rec in places.items():
            if rec.values.get("parent_id") in inside and pid not in inside:
                inside.add(pid)
                grew = True
    return inside


def _tail(child, parent) -> str:
    """子の名から親の名を落として、動いた値だけを見せる。"""
    name = str(child.values.get("name") or "")
    tail = name.replace(str(parent.values.get("name") or ""), "").strip()
    return tail.lstrip("のがはを ").strip() or name


def _find_place(lib: reader.Library, needle: str) -> str | None:
    for rec in lib.of("place"):
        if needle in (rec.id, rec.values.get("name")):
            return rec.id
    return None


def brief(lib: reader.Library, place: str, when: stamp.Stamp,
          reach: int, full: bool) -> str:
    """その場所・その年の世界を一枚に出す。**設定を頭から読み直すより早い。**

    `--full` を付けないかぎり、種別に `/裏` の付いた行は伏せる。
    本文を書くあいだは付けない。**住人が知らないことを書いてしまう。**
    """
    places = {r.id: r for r in lib.of("place")}
    here = _find_place(lib, place)
    if here is None:
        return f"「{place}」という場所がない。list --kind 場所 で見る"

    # **断面も年で見る。** `--time 4354` は 4354 年いっぱい。月日で切ると、
    # その年の後半に起きたことが、書いたばかりでも断面に出てこない
    when = stamp.Stamp(when.year, 12, 31, 23, 59, 59)

    chain = _lineage(here, places)
    inside = _descendants(here, places)
    scope = inside | set(chain)

    def visible(rec):
        return full or HIDDEN not in str(rec.values.get("kind") or "")

    def wide(rec):
        return "" if rec.values.get("place_id") in inside else "（広域）"

    def kind_of(rec):
        return str(rec.values.get("kind") or "")

    # --- 出来事を、いまの数値・続いているもの・直近・火種へ振り分ける ------
    numbers: dict[tuple, reader.Record] = {}
    ongoing, recent, tinder = [], [], []
    values: dict[str, reader.Record] = {}

    for rec in lib.of("event"):
        if rec.values.get("place_id") not in scope or not visible(rec):
            continue
        if _actor_of(rec):
            continue          # 行動は 5 節へ回す
        at = rec.values.get("time")
        if at and at > when:
            continue
        kind, end = kind_of(rec), rec.values.get("end")

        if kind.startswith("指標"):
            key = (rec.values.get("place_id"), rec.values["name"].split("　")[0])
            key = (key[0], str(rec.values["name"]).rsplit(" ", 2)[0])
            if key not in numbers or numbers[key].values["time"] <= at:
                numbers[key] = rec
        elif kind.startswith("火種/値"):
            parent = rec.values.get("parent_event_id")
            if parent and (parent not in values
                           or values[parent].values["time"] <= at):
                values[parent] = rec
        elif kind.startswith("火種"):
            if end is None or end >= when:
                tinder.append(rec)
        elif end is None or end >= when:
            ongoing.append(rec)
        elif at and (when.year - at.year) <= reach:
            recent.append(rec)

    # --- その場にいる者と、その行動 ---------------------------------------
    # 個体（群）と人物（一人ひとり）は、置き場所が違うだけで扱いは同じ
    owners = ["object", "character"]
    by_id = {}
    for table in owners:
        by_id.update({r.id: (table, r) for r in lib.of(table)})

    present = []
    for table in owners:
        for stay in lib.of(f"{table}_place"):
            start, end = stay.values.get("start"), stay.values.get("end")
            if stay.values.get("place_id") not in scope:
                continue
            if (start and start > when) or (end and end < when):
                continue
            found = by_id.get(stay.values[f"{table}_id"])
            if not found:
                continue
            owner = found[1]
            if owner.values.get("end") and owner.values["end"] < when:
                continue
            present.append((table, owner, stay))

    event_by_id = {r.id: r for r in lib.of("event")}
    deeds = []
    for deed in lib.of("event"):
        actor = _actor_of(deed)
        if not actor or actor[1] not in by_id:
            continue
        at = deed.values.get("time") or deed.values.get("start")
        if not at or at > when or (when.year - at.year) > reach:
            continue
        if deed.values.get("place_id") not in scope:
            continue
        target = event_by_id.get(deed.values.get("parent_event_id"))
        if not visible(deed) or (target is not None and not visible(target)):
            continue
        if kind_of(target or deed) == "関係":
            continue
        deeds.append((actor[1], deed, target or deed))

    # --- その場で使える語 -------------------------------------------------
    words = []
    for rec in lib.of("term"):
        limits = [rec.values.get(k) for k in
                  ("restrict_world_id", "restrict_planet_id", "restrict_place_id")]
        if any(limit and limit not in scope for limit in limits):
            continue
        kind = kind_of(rec)
        if not full and (HIDDEN in kind or kind.endswith(RETIRED)):
            continue
        words.append(rec)

    buried = sum(1 for r in lib.of("event")
                 if r.values.get("place_id") in scope and not visible(r))

    # --- 組み立て ---------------------------------------------------------
    out = [f"# 断面 / {places[here].values.get('name')} / {when.year} 年", "",
           "場所: " + " ← ".join(str(places[p].values.get("name")) for p in chain),
           f"射程: {reach} 年" + ("" if full else "（裏は伏せてある）"), ""]

    def section(title, rows):
        out.append(f"## {title}")
        out.extend(rows or ["（なし）"])
        out.append("")

    def when_of(rec):
        return rec.values["time"]

    section("1 いまの数値（分子と分母）", [
        f"- {_year(when_of(r))} {r.values['name']}{wide(r)}"
        for r in sorted(numbers.values(), key=lambda r: str(r.values["name"]))])

    section("2 続いている出来事（背景に置くもの）", [
        f"- {_year(when_of(r))} {r.values['name']}{wide(r)}"
        f"　[{kind_of(r) or '—'}]" for r in sorted(ongoing, key=when_of)])

    section(f"3 直近 {reach} 年の出来事", [
        f"- {_year(when_of(r))} {r.values['name']}{wide(r)}"
        for r in sorted(recent, key=when_of)])

    name_by_id = {r.id: str(r.values.get("name") or r.id) for r in lib.records}

    def label_of(table, rec):
        """個体は分類、人物は種族を添える。どちらか無ければ種別名で代える。

        **指し先はパスで持っているので、人に見せるときは名に戻す。**
        """
        if table == "character":
            race = rec.values.get("race_id")
            return name_by_id.get(race, race) if race else "人物"
        kind = rec.values.get("kind") or rec.values.get("kind_id")
        return name_by_id.get(kind, kind) if kind else "個体"

    section("4 その場にいる者", [
        f"- {o.values['name']}（{label_of(t, o)}）{_span(o)}{wide(s)}"
        for t, o, s in sorted(present, key=lambda p: str(p[1].values["name"]))])

    section("5 この射程での行動（何を失ったか）", [
        f"- {_year(d.values['time'])} "
        f"{by_id[a][1].values['name']}: {d.values['name']}"
        + (f"　← {e.values['name']}" if e is not d else "")
        for a, d, e in sorted(deeds, key=lambda p: p[1].values["time"])])

    section("6 張っている火種（次の一手の候補）", [
        f"- {r.values['name']}{wide(r)}"
        + (f"　→ {_tail(values[r.id], r)}"
           f"（{_year(when_of(values[r.id]))}）" if r.id in values else "")
        for r in sorted(tinder, key=when_of)])

    section("7 ここで使える語",
            ["- " + "、".join(str(r.values["name"]) for r in words)]
            if words else [])

    if not full:
        out += ["## 8 ここからは見えないこと", f"{buried} 件（--full で出る）", ""]
    return "\n".join(out)


# ------------------------------------------------------- 顔ぶれ（書く前の材料）

def cast(lib: reader.Library, story: str, when: stamp.Stamp | None,
         count: int, full: bool) -> str:
    """**その話に出せる顔ぶれと、それぞれの直近の動き。**

    作品が立つ場所の**一つ上**を基準にして、その配下の場所に
    その時点で居る人物・個体を集め、一人（一群）ずつ直近 `count` 件の
    出来事を並べる。`brief` が「世界がどうなっているか」なら、
    こちらは「誰がいて、その人に何が起きたか」を出す。

    年で見る（`--time 4354` はその年いっぱい）。`--full` を付けないかぎり、
    種別に `/裏` の付いた出来事は伏せる。**本文を書くあいだは付けない。**
    """
    story_rec = next((r for r in lib.of("story")
                      if story in (r.id, r.values.get("name"))), None)
    if story_rec is None:
        names = "、".join(sorted(str(r.id) for r in lib.of("story")))
        return f"「{story}」という作品がない。作品: {names}"

    places = {r.id: r for r in lib.of("place")}
    here = story_rec.values.get("place_id")
    if here not in places:
        return f"「{story}」の meta.md に、台帳にある場所が書かれていない"

    # 基準は作品の立つ場所の一つ上。無ければその場所そのもの
    base = places[here].values.get("parent_id") or here
    if base not in places:
        base = here
    inside = _descendants(base, places)

    if when is None:
        when = story_rec.values.get("start")
    if when is None:
        return f"「{story}」の meta.md に始まりの年がない。--time で渡す"

    # **顔ぶれは年で見る。** `--time 4354` は 4354 年いっぱいを指す。
    # 月日まで刻むと、同じ年の後半に起きたことが材料から落ちる
    when = stamp.Stamp(when.year, 12, 31, 23, 59, 59)

    def visible(rec):
        return full or HIDDEN not in str(rec.values.get("kind") or "")

    owners = ["object", "character"]
    by_id = {}
    for table in owners:
        by_id.update({r.id: (table, r) for r in lib.of(table)})

    present = []
    for table in owners:
        for stay in lib.of(f"{table}_place"):
            if stay.values.get("place_id") not in inside:
                continue
            start, end = stay.values.get("start"), stay.values.get("end")
            if (start and start > when) or (end and end < when):
                continue
            found = by_id.get(stay.values[f"{table}_id"])
            if not found:
                continue
            owner = found[1]
            if owner.values.get("end") and owner.values["end"] < when:
                continue
            present.append((table, owner, stay.values["place_id"]))

    # 同じ者が二つの居場所で挙がることがあるので、いちばん内側の一件に寄せる
    unique = {}
    for table, owner, place_id in present:
        unique.setdefault(owner.id, (table, owner, place_id))

    event_by_id = {r.id: r for r in lib.of("event")}
    deeds: dict[str, list] = {}
    for deed in lib.of("event"):
        actor = _actor_of(deed)
        if not actor or actor[1] not in unique:
            continue
        at = deed.values.get("time") or deed.values.get("start")
        target = event_by_id.get(deed.values.get("parent_event_id")) or deed
        if not at or at > when or not visible(deed) or not visible(target):
            continue
        deeds.setdefault(actor[1], []).append((at, target, deed))

    out = [f"# 顔ぶれ / {story} / {when.year} 年", "",
           "基準: " + str(places[base].values.get("name"))
           + f"（{places[here].values.get('name')} の一つ上）",
           f"配下の場所: {len(inside)} / 直近 {count} 件ずつ"
           + ("" if full else "（裏は伏せてある）"), ""]

    if not unique:
        out += ["（その時点で、配下の場所に誰もいない）", ""]
        return "\n".join(out)

    name_by_id = {r.id: str(r.values.get("name") or r.id) for r in lib.records}

    def label_of(table, rec):
        """指し先はパスで持っているので、人に見せるときは名に戻す。"""
        if table == "character":
            race = rec.values.get("race_id")
            return name_by_id.get(race, race) if race else "人物"
        kind = rec.values.get("kind") or rec.values.get("kind_id")
        return name_by_id.get(kind, kind) if kind else "個体"

    for owner_id, (table, owner, place_id) in sorted(
            unique.items(), key=lambda p: str(p[1][1].values["name"])):
        out.append(f"## {owner.values['name']}"
                   f"（{label_of(table, owner)}）{_span(owner)}")
        out.append(f"- いま: {places[place_id].values.get('name')}")
        for key, label in (("desire", "欲"), ("fear", "恐れ"),
                           ("lie", "嘘"), ("need", "必要")):
            if owner.values.get(key):
                out.append(f"- {label}: {owner.values[key]}")
        rows = sorted(deeds.get(owner_id, []), key=lambda p: p[0])[-count:]
        if rows:
            out.append("- 直近の出来事:")
            for at, target, _ in reversed(rows):
                out.append(f"  - {_year(at)} {target.values['name']}"
                           f"　[{target.values.get('kind') or '—'}]")
        else:
            out.append("- 直近の出来事: （まだ無い）")
        out.append("")
    return "\n".join(out)


# --------------------------------------------- その場・その時（結合で一度に）

# 場所（と配下）・出来事・人物／個体を一度に結ぶ。**場所が要**。
# 配下は `parent_id` を再帰でたどる。出来事は場所を持っているので、
# ここに人物・個体を外部結合すれば「誰が何をしたか」までそろう
_SCOPE_CTE = """
WITH RECURSIVE inside(id) AS (
    SELECT id FROM place WHERE id = :root
    UNION ALL
    SELECT p.id FROM place p JOIN inside ON p.parent_id = inside.id
),
up(id, parent_id) AS (
    SELECT id, parent_id FROM place WHERE id = :root
    UNION ALL
    SELECT p.id, p.parent_id FROM place p JOIN up ON p.id = up.parent_id
),
scope(id) AS (SELECT id FROM inside UNION SELECT id FROM up)
"""

# 場所（配下と、上にさかのぼった分）・出来事・人物／個体を一度に結ぶ。
# **場所が要。** 出来事は場所を持っているので、ここに人物・個体を
# 外部結合すれば「誰が何をしたか」までそろう
_SCENE_SQL = _SCOPE_CTE + """
SELECT p.name         AS place_name,
       p.location_key AS location_key,
       e.time         AS time,
       e.name         AS event_name,
       e.kind         AS kind,
       c.name         AS character_name,
       o.name         AS object_name,
       (e.place_id NOT IN (SELECT id FROM inside)) AS wide
FROM event e
JOIN scope              ON scope.id = e.place_id
JOIN place p            ON p.id = e.place_id
LEFT JOIN "character" c ON c.id = e.character_id
LEFT JOIN "object" o    ON o.id = e.object_id
WHERE e.time <= :until AND e.time >= :since
ORDER BY e.time, p.name, e.name
"""

# その時そこに居た者。居場所の表を場所で絞り、期間で切る
_PRESENT_SQL = _SCOPE_CTE + """
SELECT who.name, who.kind, p.name,
       (who.place_id NOT IN (SELECT id FROM inside)) AS wide
FROM (
    SELECT s.place_id, s.start, s.end, c.name AS name, '人物' AS kind
    FROM character_place s JOIN "character" c ON c.id = s.character_id
    UNION ALL
    SELECT s.place_id, s.start, s.end, o.name AS name, '個体' AS kind
    FROM object_place s JOIN "object" o ON o.id = s.object_id
) AS who
JOIN scope   ON scope.id = who.place_id
JOIN place p ON p.id = who.place_id
WHERE (who.start IS NULL OR who.start <= :until)
  AND (who.end IS NULL OR who.end >= :until)
ORDER BY who.kind, who.name
"""


def _place_root(engine, needle: str) -> tuple[str, str] | None:
    """場所を、id・名前・一意テキスト（`location_key`）のどれでも引く。"""
    from sqlalchemy import text

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, name FROM place "
            "WHERE id = :n OR name = :n OR location_key = :n LIMIT 1"
        ), {"n": needle}).fetchone()
    return (row[0], row[1]) if row else None


def scene(engine, place: str, when: stamp.Stamp, reach: int) -> str:
    """**場所と時刻を指定して、そこの要素を一度に引く。**

    場所・出来事・人物／個体を db の側で結合して取る
    （`brief` が読み物なのに対し、こちらは素の行）。
    場所は名前でも id でも、一意テキスト（`w4/p1/x-/y-/z-`）でもよい。
    """
    from sqlalchemy import text

    found = _place_root(engine, place)
    if found is None:
        return f"「{place}」という場所がない。list --kind 場所 で見る"
    root, name = found

    until = stamp.Stamp(when.year, 12, 31, 23, 59, 59).to_int()
    since = stamp.Stamp(when.year - reach, 1, 1, 0, 0, 0).to_int()

    out = [f"# その場 / {name} / {when.year} 年（射程 {reach} 年）", ""]
    with engine.connect() as conn:
        present = conn.execute(text(_PRESENT_SQL),
                               {"root": root, "until": until}).fetchall()
        rows = conn.execute(text(_SCENE_SQL), {
            "root": root, "until": until, "since": since}).fetchall()

    out.append("## 居る者")
    out += [f"- {who}（{kind}）@ {where}" + ("（広域）" if wide else "")
            for who, kind, where, wide in present] or ["（なし）"]
    out += ["", "## 出来事と行動"]
    if not rows:
        out.append("（なし）")
    for row in rows:
        actor = row.character_name or row.object_name
        at = stamp.Stamp.from_int(row.time)
        out.append(
            f"- {at.year} {row.place_name}" + ("（広域）" if row.wide else "")
            + (f"[{row.location_key}]" if row.location_key else "")
            + f": {row.event_name}"
            + (f"　← {actor}" if actor else "")
            + (f"　[{row.kind}]" if row.kind else ""))
    return "\n".join(out)


# ---------------------------------------------------------------- 直前の話

def episodes(lib: reader.Library, story: str, before: int | None,
             count: int, body: bool) -> str:
    """**次の話を考える前に、直前の話を読む。** 既定で 10 話ぶん。

    `--before 11` を付けると 11 話より前（001〜010）を返す。付けなければ
    いちばん新しいほうから数える。`--list` を付けると原稿は出さず、
    話数と題と字数だけを並べる（どこまで書いたかの確認用）。
    """
    found = [r for r in lib.of("episode")
             if r.values.get("story_id") == story]
    if not found:
        names = "、".join(sorted(str(r.values.get("name") or r.id)
                                for r in lib.of("story"))) or "（作品がない）"
        return f"「{story}」という作品の話がない。作品: {names}"

    found.sort(key=lambda r: r.values.get("number") or 0)
    if before is not None:
        found = [r for r in found if (r.values.get("number") or 0) < before]
    found = found[-count:] if count > 0 else found

    out = [f"# 直前の話 / {story} / {len(found)} 話", ""]
    for rec in found:
        title = rec.values.get("title") or ""
        out.append(f"## 第 {rec.values.get('number')} 話"
                   + (f"　{title}" if title else "")
                   + f"（{rec.values.get('letters') or 0} 字）")
        out.append("")
        if body:
            out += [rec.values.get("text", ""), ""]
    return "\n".join(out)


# ---------------------------------------------------------------- 開く

def start(lib: reader.Library, story: str, when: stamp.Stamp | None,
          count: int, reach: int) -> str:
    """**作業を開くときに読むものを、一度に全部出す。**

    `core/CLAUDE.md`「書く前に必ず読む」が並べているうち、台帳から出せる
    ぶん（作品の企画・プロット・直前の話・断面・顔ぶれ）をまとめて返す。
    一つずつ呼ぶと、同じマークダウンを何度も読み直すうえに、
    呼ぶ側の往復も増える。**読むものが決まっているなら、一度で出す。**

    未同期の話があれば、何も出さずにそれだけを返す（`brief` と同じ扱い）。
    裏は伏せたままで、ここに `--full` は無い。本文を書く前に読むものだから。
    """
    def nest(block: str) -> str:
        """挟み込むぶん、中の見出しを一段ずつ下げる。"""
        return "\n".join("#" + line if line.startswith("#") else line
                          for line in block.splitlines())

    warning = sync_warning(lib, story)
    if warning:
        return warning

    story_rec = next((r for r in lib.of("story")
                      if story in (r.id, r.values.get("name"))), None)
    if story_rec is None:
        names = "、".join(sorted(str(r.id) for r in lib.of("story")))
        return f"「{story}」という作品がない。作品: {names}"

    out = [f"# 開く / {story_rec.id}", ""]

    out += ["## 企画（meta.md）", ""]
    for key, column in reader.FIELDS["story"].items():
        if key != "名" and story_rec.values.get(column) not in (None, ""):
            out.append(f"{key}: {story_rec.values[column]}")
    out += ["", story_rec.values.get("text", ""), ""]

    plot = os.path.join(NOVELS, "stories", str(story_rec.id), "plot.md")
    if os.path.exists(plot):
        with open(plot, encoding="utf-8") as fh:
            out += ["## プロット（plot.md）", "", fh.read().rstrip(), ""]

    out += [nest(episodes(lib, str(story_rec.id), None, count, body=True)),
            ""]

    here = story_rec.values.get("place_id")
    if when is None:
        when = story_rec.values.get("start")
    if here and when is not None:
        places = {r.id: r for r in lib.of("place")}
        name = str(places[here].values.get("name") or here) \
            if here in places else str(here)
        out += [nest(brief(lib, name, when, reach, False)), ""]
        out += [nest(cast(lib, str(story_rec.id), when, 5, False)), ""]
    return "\n".join(out)


# ---------------------------------------------------------------- 同期

SYNC_NOTE = (
    "**未同期の話がある。** その話で起きたことが台帳へ戻っていないので、\n"
    "いま材料を読んでも、断面も顔ぶれも古いままになる。\n"
    "先にモード 3（世界観更新）をやる: 出来事・人物行動を書き足して\n"
    "`python3 tools/novel.py check` を通し、そのあと\n"
    "`python3 tools/novel.py sync <作品名>/<話数>` でフラグを立てる。\n"
    "どうしても先に読むだけ読みたいときは `--skip-sync` を付ける。")


def unsynced(lib: reader.Library, story: str | None = None) -> list:
    """同期フラグの立っていない話を、話数の順に返す。"""
    found = [r for r in lib.of("episode") if not r.values.get("synced")]
    if story:
        found = [r for r in found if r.values.get("story_id") == story]
    return sorted(found, key=lambda r: (str(r.values.get("story_id")),
                                        r.values.get("number") or 0))


def sync_warning(lib: reader.Library, story: str | None = None) -> str:
    """未同期があれば知らせ文を返す。無ければ空。"""
    rows = unsynced(lib, story)
    if not rows:
        return ""
    lines = [f"- {r.values.get('story_id')} / 第 {r.values.get('number')} 話"
             + (f"　{r.values.get('title')}" if r.values.get("title") else "")
             for r in rows]
    return "\n".join([SYNC_NOTE, ""] + lines)


# ---------------------------------------------------------------- 索引

def index(lib: reader.Library, world: str) -> str:
    """`glossary.md` の中身を作る。**手で書かない。ここから作り直す。**"""
    rows = [f"# 用語索引 / {world}", "",
            "<!-- 自動生成。`python3 tools/novel.py index` で作り直す。手で書かない -->",
            "",
            "**中身はここにない。** 一語一ファイルで `novels/terms/` にある。",
            "語を足すときは、索引ではなくファイルのほうを作る。", ""]

    place_name = {r.id: str(r.values.get("name") or r.id) for r in lib.of("place")}
    terms = {r.id: r for r in lib.of("term")}

    def path_of(rec) -> str:
        """上位の語からたどった並び。`魔力 › 魔力切れ`"""
        chain, seen = [], set()
        while rec is not None and rec.id not in seen:
            seen.add(rec.id)
            chain.append(str(rec.values.get("name") or rec.id))
            rec = terms.get(str(rec.values.get("parent_term_id") or ""))
        return " › ".join(reversed(chain))

    groups: dict[str, list[reader.Record]] = {}
    for rec in lib.of("term"):
        limit = rec.values.get("restrict_world_id")
        if limit and place_name.get(limit, limit) != world:
            continue
        groups.setdefault(str(rec.values.get("kind") or "その他"), []).append(rec)

    for kind in sorted(groups):
        rows += [f"## {kind}", "", "| 語 | 星 | 一言 |", "| --- | --- | --- |"]
        for rec in sorted(groups[kind], key=path_of):
            summary = next((l.strip() for l in rec.values.get("text", "").splitlines()
                            if l.strip() and not l.startswith("#")
                            and not l.startswith("|")), "")
            star = rec.values.get("restrict_planet_id") or "—"
            rows.append(f"| {path_of(rec)} | {place_name.get(star, star)} "
                        f"| {summary[:70]} |")
        rows.append("")
    return "\n".join(rows)


# ---------------------------------------------------------------- 雛形

# 本文はデータを持たない。雛形もマークダウンの見出しから始める
EPISODE_TEMPLATE = """<!-- 置き場所: novels/stories/<作品名>/episodes/<話数>.md（`3.md`。ゼロ埋めしない） -->
<!-- **このファイルにデータ（`# data`）を書かない。** 原稿だけを置く。
     話数はファイル名、題は下の見出しから台帳に入る（core/chronicle.md）。
     書きはじめる前に、直前の 10 話を読む:
     python3 tools/novel.py episodes --story <作品名> -->

# 第 <N> 話　<サブタイトル>

<!-- 作業メモ。本文には残さない
- 変化するもの:
- 引きの型:
- 前話からの接続:
-->

<本文をここから。冒頭 3 行で場所・時間・誰がいるかを示す>
"""


def template(table: str) -> str:
    if table == "episode":
        return EPISODE_TEMPLATE
    fields = reader.FIELDS[table]
    head = ["# data"] + [f"{k}:" for k in fields] + ["# text", "",
                      f"# （{reader.LABEL[table]}の名）", "",
                      "（データの下は人間が読む文章。",
                      "  データに書いたことを繰り返さない）"]
    where = {
        "place": "novels/worlds/<世界線>/**/<場所>/<場所>.md",
        "event": ("novels/worlds/<世界線>/**/<場所>/events/{時刻}_{名}.md"
                  "（行動なら <個体>/events/ か <人名>/events/ の下）"),
        "kind": "novels/objects/<世界線>/<種別>.md",
        "object": "novels/objects/<世界線>/**/<個体>/<個体>.md",
        "object_place": "novels/objects/<世界線>/**/<個体>/places/{時刻}_{場所}.md",
        "character": "novels/characters/<出身地>/**/<人名>/<人名>.md",
        "character_place":
            "novels/characters/<出身地>/**/<人名>/places/{時刻}_{場所}.md",
        "term": "novels/terms/**/<語>/<語>.md",
        "story": "novels/stories/<作品名>/meta.md",
        "episode": "novels/stories/<作品名>/episodes/<話数>.md",
    }[table]
    note = ("<!-- 他のレコードを指す欄には、その置き場所のパスを書く"
            "（`worlds/<世界線>/…/<場所>`）。名前では書かない -->")
    return (f"<!-- 置き場所: {where} -->\n{note}\n"
            + "\n".join(head) + "\n")


# ---------------------------------------------------------------- 書き出す

# **持ち主から置き場所を組み直す表は要らなくなった。**
# id が置き場所そのものなので、`_record_path` が id から直に組む。

# データに、限られた欄だけを書くレコード。話は原稿が中身なので、
# 台帳の都合で持つ `同期` だけをデータに残す（話数はファイル名、
# 題と字数は原稿から採り直すので書かない）
HEAD_KEYS = {"episode": ("同期",)}


def _record_path(table: str, rec_id: str, row) -> str:
    """id から置き場所を組む。**id がそのまま置き場所（パス）である。**

    ディレクトリが一件になるレコード（場所・個体・人物・作品）は、その
    ディレクトリの中の同じ名の md。ファイルが一件になるレコード（出来事・
    居場所・種別・話）は、id に `.md` を付けるだけ。

    語だけは両方ありうる（`terms/魔力/魔力.md` と `terms/魔力/魔力切れ.md`）。
    ディレクトリが実際にあるかで決める。
    """
    here = os.path.join(NOVELS, *rec_id.split("/"))
    if table == "story":
        return os.path.join(here, "meta.md")
    if table in ("place", "object", "character"):
        return os.path.join(here, f"{rec_id.rsplit('/', 1)[-1]}.md")
    if table == "term":
        if os.path.isdir(here):
            return os.path.join(here, f"{rec_id.rsplit('/', 1)[-1]}.md")
        return here + ".md"
    return here + ".md"


def dump(engine, lib: reader.Library) -> list[str]:
    """DB の行をマークダウンへ書き戻す。**書き出したパスを返す。**

    データの欄は `reader.FIELDS` を逆に辿って作る。**他を指す欄は id、
    つまり `novels/` からの相対パスをそのまま書く。**
    時刻は `y/mm/dd hh:mm:ss` で書く。内容が変わらないファイルは書き直さない。

    **置き場所は、まず今のマークダウンから探す。** `terms/` のように、
    id に出ない見た目だけの整理フォルダ（`ノウル` `地球` など）を人が
    自由に挟めるところがあるので、`id` からの逆算だけでは元の場所に
    戻せない。db にしかない新しい行（直接足された分）だけ、id から
    素直に場所を組む。
    """
    from sqlalchemy.orm import Session

    existing_path = {(rec.table, rec.id): rec.path for rec in lib.records}

    with Session(engine) as session:
        written = []
        for table, model in reader.MODELS.items():
            for row in session.query(model).order_by(model.id):
                head = {}
                for key, column in reader.FIELDS[table].items():
                    if key == "名":
                        continue
                    value = getattr(row, column, None)
                    if value in (None, ""):
                        continue
                    # **他のレコードを指す欄は、id（＝置き場所のパス）を
                    # そのまま書く。** 名前に戻さない。名前は重なるし、
                    # 変えれば指し先が黙って外れる
                    if isinstance(value, stamp.Stamp):
                        value = str(value)
                    elif isinstance(value, decimal.Decimal):
                        value = float(value)
                        if value == int(value):
                            value = int(value)
                    elif isinstance(value, float) and value == int(value):
                        value = int(value)
                    elif isinstance(value, bool):
                        value = "true" if value else "false"
                    head[key] = value
                path = existing_path.get((table, row.id)) \
                    or _record_path(table, row.id, row)
                if table in HEAD_KEYS:
                    head = {k: head.get(k, False) for k in HEAD_KEYS[table]}
                text_body = (row.text or "").strip()
                content = ("# data\n"
                           + "".join(f"{k}: {v}\n" for k, v in head.items())
                           + "# text\n\n" + text_body + "\n")
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as fh:
                        if fh.read() == content:
                            continue
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(content)
                written.append(os.path.relpath(path, REPO))
    return written


# ------------------------------------------------------------ 本文（stories）

def story_rows(engine) -> list:
    """db の作品をぜんぶ返す（`schema.Story` の行）。"""
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        rows = session.query(schema.Story).order_by(schema.Story.id).all()
        session.expunge_all()
        return rows


def episode_rows(engine, story: str | None = None) -> list:
    """db の話を返す（`schema.Episode` の行）。`story` で作品を絞れる。"""
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        query = session.query(schema.Episode)
        if story:
            query = query.filter(schema.Episode.story_id == story)
        rows = query.order_by(schema.Episode.story_id,
                              schema.Episode.number).all()
        session.expunge_all()
        return rows


def _split_episode(path: str) -> tuple[str, int]:
    """話の指し方を、作品の id と話数へ解く。

    `<作品名>/3` でも `stories/<作品名>/episodes/3.md` でもよい。
    **戻す作品は id**、つまり `stories/<作品名>` の形にそろえる。
    """
    rel = path.replace(os.sep, "/").strip("/")
    if rel.endswith(".md"):
        rel = rel[:-len(".md")]
    rel = rel.replace("/episodes/", "/")
    if rel.startswith("stories/"):
        rel = rel[len("stories/"):]
    story, _, number = rel.rpartition("/")
    if not story or not number.isdigit():
        raise ValueError("話の指し方は `<作品名>/<話数>` "
                         "（`stories/<作品名>/episodes/3.md` でもよい）")
    return f"stories/{story}", int(number)


def read_episode(engine, path: str) -> str:
    """話を一件、原稿のまま読む。無ければ `LookupError`。"""
    story, number = _split_episode(path)
    for row in episode_rows(engine, story):
        if row.number == number:
            return row.text
    raise LookupError(f"「{story}」の {number} 話は db に無い")


def set_synced(engine, path: str, value: bool) -> str:
    """話の同期フラグを立てる・下ろす。**戻り値は id。**

    立てるのは、その話の出来事・人物行動を台帳へ戻したあと
    （モード 3）。コードは中身を作れないので、ここは人が通す関門になる。
    """
    from sqlalchemy.orm import Session

    story, number = _split_episode(path)
    with Session(engine) as session:
        row = session.get(schema.Episode, f"{story}/episodes/{number}")
        if row is None:
            raise LookupError(f"「{story}」の {number} 話は db に無い")
        row.synced = value
        session.commit()
        return row.id


def write_episode(engine, path: str, text: str, synced: bool = False) -> str:
    """話を一件、db へ書き入れる（無ければ作る）。**戻り値は id。**

    マークダウンはここでは触らない。ファイルになるのは `save`（書き出し）。
    題と字数は原稿から採り直す。**同期フラグは既定で下りる**（手で書いた話は、
    モード 3 を通すまで未同期）。自動生成で出来事まで一緒に積んだときだけ
    `synced=True` で書く。
    """
    from sqlalchemy.orm import Session

    story, number = _split_episode(path)
    if not text.endswith("\n"):
        text += "\n"

    with Session(engine) as session:
        if session.get(schema.Story, story) is None:
            raise LookupError(f"「{story}」という作品が db に無い。"
                              "先に meta.md を作る")
        rec_id = f"{story}/episodes/{number}"
        row = session.get(schema.Episode, rec_id)
        if row is None:
            row = schema.Episode(id=rec_id, story_id=story, number=number)
            session.add(row)
        row.text = text
        row.title = reader._episode_title(text)
        row.letters = len(text)
        row.synced = synced
        session.commit()
    return rec_id


# ---------------------------------------------------------------- まとめて流す

def batch(path: str, keep_going: bool) -> int:
    """**命令を何本も、一度の読み込みで流す。**

    一行が一命令で、`novel.py` に渡すのと同じ書き方をする（`show 采配`）。
    空行と `#` から先は読み飛ばす。マークダウンを読むのは一度きりなので、
    引きたいものが何件もあるときは、一件ずつ呼ぶより速いし、呼ぶ側の
    往復も一回で済む。

    **見るためのもので、書き換えを積むためのものではない。** 途中で
    `load` や `text` を挟んでも、あとに続く命令が見るのは最初に読んだ
    マークダウンのままになる。
    """
    import shlex

    source = (sys.stdin.read() if path == "-"
              else open(path, encoding="utf-8").read())
    lines = []
    for line in source.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            lines.append(line)
    if not lines:
        print("流す命令がない", file=sys.stderr)
        return 1

    lib = reader.read_library(NOVELS)
    worst = 0
    for line in lines:
        print(f"$ novel.py {line}")
        code = main(shlex.split(line), lib=lib)
        print()
        if code:
            worst = code
            if not keep_going:
                return code
    return worst


# ---------------------------------------------------------------- 入口

def main(argv=None, lib: "reader.Library | None" = None):
    """**一回ぶんの命令を実行する。**

    `lib` を渡すと、マークダウンを読み直さずにそれを使う。`batch` が
    同じ読み込みで何本も流すために使う入口で、普段は渡さなくてよい。
    """
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="不備を探す")
    sub.add_parser("load", help="**作業開始時。** マークダウンを db へ読み込む")
    sub.add_parser("build", help="load と同じ（旧い呼び名）")
    sub.add_parser("save", help="**作業終了時。** db をマークダウンへ書き出す")

    p = sub.add_parser("stories", help="作品と話の一覧を出す")
    p.add_argument("--work", help="作品名で絞る")

    p = sub.add_parser("read", help="話を一件読む（db から）")
    p.add_argument("path", help="<作品名>/<話数>（`めぐる旅路…/3`）")

    p = sub.add_parser("write", help="話を一件書く（db へ）")
    p.add_argument("path", help="<作品名>/<話数>（`めぐる旅路…/3`）")
    p.add_argument("--file", required=True,
                   help="本文の入ったファイル。`-` で標準入力")
    p.add_argument("--synced", action="store_true",
                   help="出来事まで一緒に積んだ自動生成のときだけ付ける。"
                        "手で書いたときは付けない（既定は未同期）")

    p = sub.add_parser("sync", help="話の同期フラグを立てる（モード 3 のあと）")
    p.add_argument("path", nargs="?", help="<作品名>/<話数>。省くと未同期の一覧")
    p.add_argument("--off", action="store_true", help="逆に下ろす")
    p.add_argument("--story", help="一覧を作品で絞る")

    p = sub.add_parser("brief", help="断面を出す")
    p.add_argument("--skip-sync", action="store_true",
                   help="未同期の話があっても止まらない")
    p.add_argument("--place", required=True)
    p.add_argument("--time", required=True)
    p.add_argument("--reach", type=int, default=60)
    p.add_argument("--full", action="store_true",
                   help="裏も出す。**本文を書くあいだは付けない**")

    p = sub.add_parser("cast", help="その話に出せる顔ぶれと、直近の出来事")
    p.add_argument("--skip-sync", action="store_true",
                   help="未同期の話があっても止まらない")
    p.add_argument("--story", required=True)
    p.add_argument("--time", help="付けなければ作品の始まりの年")
    p.add_argument("--count", type=int, default=5,
                   help="一人（一群）あたり何件（既定 5）")
    p.add_argument("--full", action="store_true",
                   help="裏も出す。**本文を書くあいだは付けない**")

    p = sub.add_parser("scene", help="場所と時刻を指定して、そこの要素を結合で引く")
    p.add_argument("--place", required=True,
                   help="場所の名前・id・一意テキスト（`w4/p1/x-/y-/z-`）")
    p.add_argument("--time", required=True)
    p.add_argument("--reach", type=int, default=60)

    p = sub.add_parser("list", help="一覧")
    p.add_argument("--kind", required=True, choices=sorted(KINDS))
    p.add_argument("--world")

    p = sub.add_parser("show", help="一件読む。**id は並べて渡せる**")
    p.add_argument("id", nargs="+")

    p = sub.add_parser("template", help="雛形を出す")
    p.add_argument("--kind", required=True, choices=sorted(KINDS))

    p = sub.add_parser("episodes", help="直前の話を読む。**次の話を考える前に**")
    p.add_argument("--skip-sync", action="store_true",
                   help="未同期の話があっても止まらない")
    p.add_argument("--story", required=True)
    p.add_argument("--before", type=int,
                   help="この話数より前だけ。付けなければ最新から数える")
    p.add_argument("--count", type=int, default=10, help="何話ぶん（既定 10）")
    p.add_argument("--list", action="store_true",
                   help="原稿を出さず、話数と題と字数だけ並べる")

    p = sub.add_parser("index", help="用語索引を書き出す")
    p.add_argument("--world", required=True)

    p = sub.add_parser("events", help="出来事と行動を、時刻か id で引く")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--time", help="その時（`4354` で年、`4354/09/28` で日）")
    g.add_argument("--of", help="この id に掛かるもの（場所・人物・個体・出来事）")

    p = sub.add_parser("show-id", help="id 一件を、どの表からでも引く")
    p.add_argument("id")

    p = sub.add_parser("text", help="レコードの本文（text 欄）を入れ替える")
    p.add_argument("id")
    p.add_argument("--file", required=True,
                   help="本文の入ったファイル。`-` で標準入力")

    p = sub.add_parser(
        "start", help="**作業開始の一手。** load してから、読むものを一度に出す")
    p.add_argument("--story", required=True)
    p.add_argument("--time", help="付けなければ作品の始まりの年")
    p.add_argument("--count", type=int, default=10,
                   help="直前の話を何話ぶん（既定 10）")
    p.add_argument("--reach", type=int, default=60)

    p = sub.add_parser("batch", help="命令を何本も、一度の読み込みで流す")
    p.add_argument("--file", default="-",
                   help="一行に一命令。`#` から先は覚え書き。`-` で標準入力")
    p.add_argument("--keep-going", action="store_true",
                   help="途中で止まらず最後まで流す")

    sub.add_parser("dump", help="db の行をマークダウンへ書き戻す")

    args = ap.parse_args(argv)

    if args.command == "template":
        print(template(KINDS[args.kind]), end="")
        return 0

    if args.command == "batch":
        return batch(args.file, args.keep_going)

    if lib is None:
        lib = reader.read_library(NOVELS)

    if args.command == "check":
        errors = inspect(lib)
        for line in errors:
            print(f"error: {line}")
        counts = ", ".join(
            f"{reader.LABEL[t]} {len(lib.of(t))}" for t in reader.MODELS
            if lib.of(t))
        print(f"{counts or 'レコードなし'} / 本文 {len(lib.stories)} 件")
        print(f"error {len(errors)} 件")
        return 1 if errors else 0

    if args.command in ("build", "load"):
        errors = inspect(lib)
        if errors:
            print("error が残っているので組めない。check を先に通す", file=sys.stderr)
            return 1
        build(lib)
        print(f"{os.path.relpath(DB, REPO)} を組み直した"
              f"（レコード {len(lib.records)}）")
        return 0

    # **読み出す前に同期を見る。** 未同期の話があると、断面も顔ぶれも
    # その話の前のままになる（core/workflow.md 2-0）
    if args.command in ("brief", "cast", "episodes") and not args.skip_sync:
        warning = sync_warning(lib, getattr(args, "story", None))
        if warning:
            print(warning, file=sys.stderr)
            return 1

    if args.command == "brief":
        print(brief(lib, args.place, reader.parse_time(args.time),
                    args.reach, args.full))
        return 0

    if args.command == "cast":
        print(cast(lib, args.story,
                   reader.parse_time(args.time) if args.time else None,
                   args.count, args.full))
        return 0

    if args.command == "scene":
        if not os.path.exists(DB):
            build(lib)
        print(scene(schema.open_db(DB), args.place,
                    reader.parse_time(args.time), args.reach))
        return 0

    if args.command == "list":
        table = KINDS[args.kind]
        for rec in sorted(lib.of(table), key=lambda r: r.id):
            if args.world and args.world not in str(rec.path):
                continue
            name = rec.values.get("name") or rec.id
            print(f"{rec.id}\t{name}\t{rec.values.get('kind') or ''}")
        return 0

    if args.command == "show":
        missing = []
        for wanted in args.id:
            for rec in lib.records:
                if wanted in (rec.id, rec.values.get("name")):
                    print(f"# {reader.LABEL[rec.table]} / {rec.id}")
                    print(f"# {os.path.relpath(rec.path, REPO)}\n")
                    for key, column in reader.FIELDS[rec.table].items():
                        if rec.values.get(column) not in (None, ""):
                            print(f"{key}: {rec.values[column]}")
                    print("\n" + rec.values.get("text", ""))
                    break
            else:
                missing.append(wanted)
        for wanted in missing:
            print(f"「{wanted}」が見つからない", file=sys.stderr)
        return 1 if missing else 0

    if args.command == "start":
        # **作業開始の一手。** `load` と同じく db を組み直してから出す
        errors = inspect(lib)
        if errors:
            print("error が残っているので組めない。check を先に通す",
                  file=sys.stderr)
            return 1
        build(lib)
        print(start(lib, args.story,
                    reader.parse_time(args.time) if args.time else None,
                    args.count, args.reach))
        return 0

    if args.command == "episodes":
        print(episodes(lib, args.story, args.before, args.count,
                       body=not args.list))
        return 0

    if args.command == "index":
        out = os.path.join(NOVELS, "worlds", args.world, "glossary.md")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(index(lib, args.world) + "\n")
        print(f"{os.path.relpath(out, REPO)} を書き直した")
        return 0

    if args.command in ("events", "show-id", "text"):
        if not os.path.exists(DB):
            build(lib)
        engine = schema.open_db(DB)
        try:
            if args.command == "events":
                if args.time:
                    rows = query.events_at(engine, args.time)
                    print(query.show_events(rows, f"その時の出来事 / {args.time}"))
                else:
                    rows = query.events_of(engine, args.of)
                    print(query.show_events(rows, f"掛かる出来事 / {args.of}"))
            elif args.command == "show-id":
                table, row = query.record(engine, args.id)
                print(query.show_record(table, row))
            else:
                body = (sys.stdin.read() if args.file == "-"
                        else open(args.file, encoding="utf-8").read())
                rec_id = query.set_text(engine, args.id, body)
                print(f"{rec_id} の本文を入れ替えた（save で md に出る）")
        except (LookupError, ValueError, stamp.StampError) as err:
            print(err, file=sys.stderr)
            return 1
        return 0

    if args.command == "sync":
        if args.path is None:
            warning = sync_warning(lib, args.story)
            print(warning or "未同期の話はない")
            return 1 if warning else 0
        if not os.path.exists(DB):
            build(lib)
        engine = schema.open_db(DB)
        try:
            rec_id = set_synced(engine, args.path, not args.off)
        except (LookupError, ValueError) as err:
            print(err, file=sys.stderr)
            return 1
        print(f"{rec_id} の同期フラグを"
              f"{'下ろした' if args.off else '立てた'}（save で md に出る）")
        return 0

    if args.command in ("stories", "read", "write"):
        if not os.path.exists(DB):
            build(lib)
        engine = schema.open_db(DB)

        if args.command == "stories":
            for row in story_rows(engine):
                if args.work and args.work != row.id:
                    continue
                print(f"{row.id}\t{row.world_id or ''}")
                for ep in episode_rows(engine, row.id):
                    print(f"  {ep.number}\t{ep.title}\t{ep.letters} 字")
            return 0

        if args.command == "read":
            warning = sync_warning(lib, _split_episode(args.path)[0])
            if warning:
                print(warning + "\n", file=sys.stderr)
            try:
                print(read_episode(engine, args.path), end="")
            except (LookupError, ValueError) as err:
                print(err, file=sys.stderr)
                return 1
            return 0

        text = (sys.stdin.read() if args.file == "-"
                else open(args.file, encoding="utf-8").read())
        try:
            rec_id = write_episode(engine, args.path, text, args.synced)
        except (LookupError, ValueError) as err:
            print(err, file=sys.stderr)
            return 1
        print(f"{rec_id} を db へ書いた（save で md に出る）")
        return 0

    if args.command == "save":
        if not os.path.exists(DB):
            print("先に load して db を組む", file=sys.stderr)
            return 1
        engine = schema.open_db(DB)
        written = dump(engine, lib)
        for path in written:
            print(f"更新: {path}")
        print(f"{len(written)} 件を書き出した" if written else "変更なし")
        return 0

    if args.command == "dump":
        if not os.path.exists(DB):
            print("先に build して db を組む", file=sys.stderr)
            return 1
        engine = schema.open_db(DB)
        written = dump(engine, lib)
        for path in written:
            print(f"更新: {path}")
        print(f"{len(written)} 件を書き直した" if written else "変更なし")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
