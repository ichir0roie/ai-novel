#!/usr/bin/env python3
"""世界の記録（年代記）。

マークダウンの台帳を SQLite に組み上げ、任意の時点の「断面」を取り出す。

    python3 tools/chronicle.py build  --world 地球系
    python3 tools/chronicle.py check  --world 地球系
    python3 tools/chronicle.py brief  --world 地球系 --star 入植星 --year 4360
    python3 tools/chronicle.py series --world 地球系 --metric 人口
    python3 tools/chronicle.py add    --world 地球系 --table event --set 年=4361 --set 星=地球 ...
    python3 tools/chronicle.py sql    --world 地球系 "select * from event limit 5"

台帳の原本は worlds/<宇宙>/records/*.md。DB は組み上げ直せるので git に入れない。
書き方と使いどころは core/chronicle.md。
"""
import argparse
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLDS_DIR = os.path.join(ROOT, "worlds")
RECORDS = "records"
DB_NAME = "chronicle.db"


# ---------------------------------------------------------------- 台帳の定義

class Col:
    """マークダウンの列一つ。md=見出し、db=SQLite の列名。"""

    def __init__(self, md, db, kind="text", req=False, ref=None):
        self.md, self.db, self.kind, self.req, self.ref = md, db, kind, req, ref


class Schema:
    def __init__(self, name, file, cols, key=None, uniq=None, inherit=()):
        self.name, self.file, self.cols = name, file, cols
        self.key = key                # 一意な id 列（あれば）
        self.uniq = uniq or ()        # 重複を禁じる列の組
        self.inherit = inherit        # 同じ id の初出から引き継ぐ列
        self.by_md = {c.md: c for c in cols}


SCHEMAS = {}


def _s(*a, **kw):
    sc = Schema(*a, **kw)
    SCHEMAS[sc.name] = sc


_s("place", "場所.md", [
    Col("id", "id", req=True), Col("名", "name", req=True), Col("星", "star"),
    Col("種別", "kind"), Col("親", "parent", ref="place"), Col("備考", "note"),
], key="id")

_s("actor", "人物.md", [
    Col("id", "id", req=True), Col("名", "name", req=True), Col("種別", "kind"),
    Col("星", "star"), Col("系統", "line"), Col("生", "born", "stamp"),
    Col("没", "died", "stamp"), Col("所属", "org"), Col("居所", "place", ref="place"),
    Col("備考", "note"),
], key="id")

_s("event", "出来事.md", [
    Col("id", "id", req=True), Col("年", "t0", "stamp", req=True), Col("終年", "t1", "stamp"),
    Col("星", "star"), Col("場所", "place", ref="place"), Col("種別", "kind"),
    Col("規模", "scale", "num"), Col("公開", "open"), Col("出来事", "summary", req=True),
    Col("関与", "actors"), Col("出典", "ref"),
], key="id")

_s("act", "行動.md", [
    Col("id", "id", req=True), Col("年", "t0", "stamp", req=True),
    Col("人物", "actor", ref="actor", req=True), Col("場所", "place", ref="place"),
    Col("行動", "deed", req=True), Col("動機", "motive"), Col("代償", "cost"),
    Col("結果", "result"), Col("公開", "open"), Col("出典", "ref"),
], key="id")

_s("metric", "指標.md", [
    Col("年", "t0", "stamp", req=True), Col("星", "star"), Col("場所", "place", ref="place"),
    Col("指標", "name", req=True), Col("値", "value", "num", req=True), Col("単位", "unit"),
    Col("出典", "ref"),
], uniq=("t0", "star", "place", "name"))

_s("bond", "関係.md", [
    Col("年", "t0", "stamp", req=True), Col("終年", "t1", "stamp"),
    Col("人物A", "a", ref="actor", req=True), Col("人物B", "b", ref="actor", req=True),
    Col("関係", "kind", req=True), Col("強度", "level", "num"), Col("出典", "ref"),
], uniq=("t0", "a", "b", "kind"))

_s("tension", "火種.md", [
    Col("id", "id", req=True), Col("年", "t0", "stamp", req=True), Col("星", "star"),
    Col("場所", "place", ref="place"), Col("名", "name"), Col("対立軸", "axis"),
    Col("値", "level", "num", req=True), Col("限界で起きること", "edge"), Col("出典", "ref"),
], key="id", uniq=("id", "t0"), inherit=("name", "axis", "edge", "star", "place"))


# ------------------------------------------------------------ 年（タイムスタンプ）

STAMP_RE = re.compile(r"(-?\d{1,5})(?:[-/](\d{1,2}))?(?:[-/](\d{1,2}))?")


def stamp_key(raw, end=False):
    """「4360」「4360-07」「4360-07-12」「3150 年ごろ」→ 並べ替え用の整数。

    end=True のときは、省かれた月日を年末・月末として埋める（範囲の上限用）。
    読めなければ None。
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = STAMP_RE.search(s)
    if not m:
        return None
    y = int(m.group(1))
    mo = int(m.group(2)) if m.group(2) else (12 if end else 0)
    d = int(m.group(3)) if m.group(3) else (31 if end else 0)
    return y * 10000 + mo * 100 + d


def year_of(key):
    return None if key is None else key // 10000


def span_key(year_key, back_years):
    return year_key - back_years * 10000


# ------------------------------------------------------ マークダウンの表を読む

CELL_SPLIT = re.compile(r"(?<!\\)\|")
SEP_CELL = re.compile(r"^:?-{2,}:?$")


def split_row(line):
    parts = CELL_SPLIT.split(line.rstrip())
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [p.strip().replace("\\|", "|") for p in parts]


def read_tables(path):
    """ファイル中のマークダウン表を全部返す。[(header, [(lineno, cells)], 表の最終行)]"""
    if not os.path.exists(path):
        return []
    out, block = [], []
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    for i, line in enumerate(lines + ["\n"], 1):
        if line.lstrip().startswith("|"):
            block.append((i, line))
            continue
        if len(block) >= 2:
            header = split_row(block[0][1])
            rows = []
            for lineno, raw in block[1:]:
                cells = split_row(raw)
                if cells and all(SEP_CELL.match(c) for c in cells if c):
                    continue
                rows.append((lineno, cells))
            out.append((header, rows, block[-1][0]))
        block = []
    return out


def load_rows(world_dir, schema, problems):
    """スキーマに合う表を全部集めて、辞書のリストにする。"""
    path = os.path.join(world_dir, RECORDS, schema.file)
    rel = os.path.relpath(path, ROOT)
    need = {c.md for c in schema.cols if c.req} or {schema.cols[0].md}
    rows = []
    for header, body, _ in read_tables(path):
        if not need.issubset(set(header)):
            continue
        for lineno, cells in body:
            if len(cells) < len(header):
                cells = cells + [""] * (len(header) - len(cells))
            rec = {"_src": f"{rel}:{lineno}"}
            for col_md, val in zip(header, cells):
                col = schema.by_md.get(col_md)
                if col:
                    rec[col.db] = val
            if not any(rec.get(c.db, "") for c in schema.cols):
                continue
            rows.append(rec)
    if not os.path.exists(path):
        problems.append(("警告", rel, "台帳がない。空として扱う"))
    return rows


def apply_inherit(schema, rows):
    """火種のように、同じ id の二行目以降で定義列を省けるようにする。"""
    if not schema.inherit or not schema.key:
        return
    first = {}
    for rec in rows:
        rid = rec.get(schema.key, "")
        if rid not in first:
            first[rid] = rec
            continue
        for db in schema.inherit:
            if not rec.get(db):
                rec[db] = first[rid].get(db, "")


# ---------------------------------------------------------------------- 設定

DEFAULT_CFG = {"現在": None, "星": {}, "光の遅れ": [], "既定の射程": 60}


def world_dir(world):
    d = os.path.join(WORLDS_DIR, world)
    if not os.path.isdir(d):
        raise SystemExit(f"そんな宇宙はない: {world}（{WORLDS_DIR} を見よ）")
    return d


def load_config(world):
    cfg = dict(DEFAULT_CFG)
    path = os.path.join(world_dir(world), RECORDS, "config.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    return cfg


def resolve_star(cfg, name):
    if not name:
        return None
    stars = cfg.get("星", {})
    if name in stars:
        return name
    for star, info in stars.items():
        if name in (info or {}).get("別名", []):
            return star
    return name


def delay_between(cfg, a, b):
    for row in cfg.get("光の遅れ", []):
        if {row[0], row[1]} == {a, b}:
            return int(row[2])
    return None


# ------------------------------------------------------------------- 組み上げ

SQL_KIND = {"text": "TEXT", "stamp": "TEXT", "num": "REAL"}


def build(world, quiet=False):
    wdir = world_dir(world)
    problems = []
    data = {}
    for name, sc in SCHEMAS.items():
        rows = load_rows(wdir, sc, problems)
        apply_inherit(sc, rows)
        data[name] = rows

    db_path = os.path.join(wdir, DB_NAME)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=MEMORY")
    for name, sc in SCHEMAS.items():
        cols = []
        for c in sc.cols:
            cols.append(f'"{c.db}" {SQL_KIND[c.kind]}')
            if c.kind == "stamp":
                cols.append(f'"{c.db}_k" INTEGER')
        cols.append('"src" TEXT')
        con.execute(f"DROP TABLE IF EXISTS {name}")
        con.execute(f"CREATE TABLE {name} ({', '.join(cols)})")

        names, holes = [], []
        for c in sc.cols:
            names.append(f'"{c.db}"')
            holes.append("?")
            if c.kind == "stamp":
                names.append(f'"{c.db}_k"')
                holes.append("?")
        names.append('"src"')
        holes.append("?")
        stmt = f"INSERT INTO {name} ({', '.join(names)}) VALUES ({', '.join(holes)})"

        payload = []
        for rec in data[name]:
            vals = []
            for c in sc.cols:
                raw = rec.get(c.db, "")
                if c.kind == "num":
                    vals.append(to_num(raw))
                else:
                    vals.append(raw)
                if c.kind == "stamp":
                    vals.append(stamp_key(raw))
            vals.append(rec["_src"])
            payload.append(vals)
        con.executemany(stmt, payload)

    con.execute("DROP TABLE IF EXISTS meta")
    con.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    con.executemany("INSERT INTO meta VALUES (?, ?)",
                    [("world", world), ("config", json.dumps(load_config(world), ensure_ascii=False))])
    for name in SCHEMAS:
        con.execute("INSERT INTO meta VALUES (?, ?)", (f"rows:{name}", str(len(data[name]))))
    con.commit()

    if not quiet:
        counts = "  ".join(f"{n}={len(data[n])}" for n in SCHEMAS)
        print(f"組み上げた: {os.path.relpath(db_path, ROOT)}")
        print(f"  {counts}")
        for level, where, msg in problems:
            print(f"  {level} {where}: {msg}")
    return con, data


def to_num(raw):
    if raw is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(raw).replace(",", ""))
    return float(m.group(0)) if m else None


# --------------------------------------------------------------------- 検査

def check(world):
    cfg = load_config(world)
    wdir = world_dir(world)
    problems = []
    data = {}
    for name, sc in SCHEMAS.items():
        rows = load_rows(wdir, sc, problems)
        apply_inherit(sc, rows)
        data[name] = rows

    ids = {name: {r.get(sc.key, "") for r in data[name]} for name, sc in SCHEMAS.items() if sc.key}
    errors, warns = [], []

    for name, sc in SCHEMAS.items():
        seen_key, seen_uniq = {}, {}
        for rec in data[name]:
            at = rec["_src"]
            for c in sc.cols:
                val = rec.get(c.db, "")
                if c.req and not val:
                    errors.append(f"{at} [{name}] 必須の「{c.md}」が空")
                if c.kind == "stamp" and val and stamp_key(val) is None:
                    errors.append(f"{at} [{name}] 「{c.md}」の年が読めない: {val}")
                if c.kind == "num" and val and to_num(val) is None:
                    errors.append(f"{at} [{name}] 「{c.md}」の値が数ではない: {val}")
                if c.ref and val:
                    for one in re.split(r"[,、/ ]+", val):
                        if one and one not in ids.get(c.ref, set()):
                            warns.append(f"{at} [{name}] 「{c.md}」の {one} が {c.ref} 台帳にない")
            # id の重複。ただし uniq を持つ台帳（火種など）は、
            # 同じ id を年ちがいで何度も書くのが正しいので見ない
            if sc.key and not sc.uniq:
                rid = rec.get(sc.key, "")
                if rid in seen_key:
                    errors.append(f"{at} [{name}] id が重複: {rid}（初出 {seen_key[rid]}）")
                else:
                    seen_key[rid] = at
            if sc.uniq:
                tup = tuple(rec.get(d, "") for d in sc.uniq)
                if tup in seen_uniq:
                    errors.append(f"{at} [{name}] 同じ組が二度ある: {tup}（初出 {seen_uniq[tup]}）")
                else:
                    seen_uniq[tup] = at
            for a, b, label in (("born", "died", "生没"), ("t0", "t1", "年と終年")):
                ka, kb = stamp_key(rec.get(a, "")), stamp_key(rec.get(b, ""))
                if ka is not None and kb is not None and kb < ka:
                    errors.append(f"{at} [{name}] {label}が逆: {rec.get(a)} → {rec.get(b)}")
            star = rec.get("star", "")
            if star and cfg.get("星") and resolve_star(cfg, star) not in cfg["星"]:
                warns.append(f"{at} [{name}] 設定にない星: {star}")

    # 場所の親が輪になっていないか
    parent = {r.get("id"): r.get("parent", "") for r in data["place"]}
    for pid in parent:
        seen, cur = {pid}, parent.get(pid, "")
        while cur:
            if cur in seen:
                errors.append(f"[place] 親が輪になっている: {pid}")
                break
            seen.add(cur)
            cur = parent.get(cur, "")

    for level, where, msg in problems:
        warns.append(f"{where}: {msg}")
    for line in warns:
        print(f"警告 {line}")
    for line in errors:
        print(f"エラー {line}")
    print(f"--- エラー {len(errors)} 件 / 警告 {len(warns)} 件")
    return 1 if errors else 0


# --------------------------------------------------------------------- 断面

def connect(world):
    path = os.path.join(world_dir(world), DB_NAME)
    if not os.path.exists(path):
        build(world, quiet=True)
    return sqlite3.connect(path)


def place_scope(con, place):
    """その場所と、その内側と、その外側（上位）の id を返す。"""
    rows = con.execute("SELECT id, name, parent FROM place").fetchall()
    parent = {r[0]: r[2] for r in rows}
    name = {r[0]: r[1] for r in rows}
    if place not in parent:
        for pid, nm in name.items():
            if nm == place:
                place = pid
                break
    if place not in parent:
        return None, None, place
    inner, stack = set(), [place]
    while stack:
        cur = stack.pop()
        inner.add(cur)
        stack += [pid for pid, par in parent.items() if par == cur and pid not in inner]
    outer, cur = set(), parent.get(place, "")
    while cur:
        outer.add(cur)
        cur = parent.get(cur, "")
    return inner, outer, place


def fmt_year(raw):
    return raw if raw else "—"


def brief(world, star, year, place=None, span=None, full=False):
    cfg = load_config(world)
    con = connect(world)
    star = resolve_star(cfg, star)
    year = year or cfg.get("現在")
    if year is None:
        raise SystemExit("--year を指定するか、config.json に「現在」を書くこと")
    lo, hi = stamp_key(year), stamp_key(year, end=True)
    if lo is None:
        raise SystemExit(f"年が読めない: {year}")
    span = span or cfg.get("既定の射程", 60)
    back = span_key(lo, span)

    inner = outer = None
    place_id = place
    if place:
        inner, outer, place_id = place_scope(con, place)
        if inner is None:
            print(f"<!-- 場所 {place} が台帳にない。星全体で出す -->")

    def in_scope(pid, allow_blank=True):
        if not pid:
            return allow_blank
        if inner is None:
            return True
        return pid in inner or pid in outer

    def wide(pid):
        return bool(outer) and pid in outer

    def visible(open_):
        """公開列は「誰から見えるか」。公然=全員 / 秘匿=誰も / 星名=その星だけ。"""
        if full:
            return True
        return (open_ or "公然") in ("公然", star)

    out = []
    w = out.append
    w(f"# 断面 / {world}・{star or '全星'}・西暦 {year} 年")
    w("")
    head = [f"射程 {span} 年（{year_of(back)}〜{year_of(hi)}）"]
    if place:
        head.append(f"場所 {place_id}（内側と外側を含む）")
    head.append("視点 " + ("作者（秘匿ふくむ）" if full else "この星の内側から見える範囲"))
    w("　/　".join(head))
    w("")

    # 1. 数値
    w("## 1. いまの数値")
    w("")
    rows = con.execute(
        "SELECT name, value, unit, t0, place, ref FROM metric "
        "WHERE t0_k <= ? AND (star = ? OR star = '') ORDER BY name, t0_k", (hi, star)).fetchall()
    latest = {}
    for name, value, unit, t0, pid, ref in rows:
        if not in_scope(pid):
            continue
        key = (name, pid)
        prev = latest.get(key)
        latest[key] = (value, unit, t0, ref, prev[:3] if prev else None)
    if latest:
        w("| 指標 | 値 | 前回 | 動き | 場所 | 出典 |")
        w("| --- | --- | --- | --- | --- | --- |")
        for (name, pid), (value, unit, t0, ref, prev) in sorted(latest.items()):
            shown = f"{trim(value)} {unit}".strip()
            if prev:
                pv, _, pt = prev
                move = "増" if value > pv else ("減" if value < pv else "横ばい")
                past = f"{trim(pv)}（{pt}）"
            else:
                move, past = "—", "—"
            w(f"| {name} | {shown}（{t0}） | {past} | {move} | {pid or '—'} | {ref or '—'} |")
    else:
        w("記録なし。")
    w("")

    # 2. 続いている出来事
    w("## 2. 続いている出来事")
    w("")
    w("<!-- この時点で始まっていて、まだ終わっていないもの -->")
    ev_cols = "id, t0, t1, star, place, kind, scale, open, summary, actors, ref"
    rows = con.execute(
        f"SELECT {ev_cols} FROM event WHERE t0_k <= ? AND t1_k IS NOT NULL AND t1_k >= ? "
        "AND (star = ? OR star = '') ORDER BY t0_k", (hi, lo, star)).fetchall()
    w(event_table(rows, in_scope, wide, visible) or "なし。")
    w("")

    # 3. 直近の出来事
    w(f"## 3. 直近の出来事（{year_of(back)}〜{year_of(hi)}）")
    w("")
    rows = con.execute(
        f"SELECT {ev_cols} FROM event WHERE t0_k <= ? AND t0_k >= ? "
        "AND (star = ? OR star = '') ORDER BY t0_k DESC", (hi, back, star)).fetchall()
    w(event_table(rows, in_scope, wide, visible) or "なし。")
    w("")

    # 4. その場にいる者
    w("## 4. その場にいる者")
    w("")
    rows = con.execute(
        "SELECT id, name, kind, line, born, died, org, place, note FROM actor "
        "WHERE (born_k IS NULL OR born_k <= ?) AND (died_k IS NULL OR died_k >= ?) "
        "AND (star = ? OR star = '')", (hi, lo, star)).fetchall()
    here = [r for r in rows if in_scope(r[7])]
    if here:
        w("| id | 名 | 種別 | 系統 | 齢／いつから | 所属 | 居所 | 備考 |")
        w("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for aid, name, kind, line, born, died, org, pid, note in sorted(here, key=lambda r: r[0]):
            bk = stamp_key(born)
            if not bk:
                age = "—"
            elif kind == "個人":
                age = f"{year_of(hi) - year_of(bk)} 歳"
            else:
                age = f"{year_of(bk)} 年〜"
            w(f"| {aid} | {name} | {kind or '—'} | {line or '—'} | {age} | {org or '—'} "
              f"| {pid or '—'} | {note or '—'} |")
    else:
        w("台帳にまだ誰もいない。")
    w("")

    # 5. 関係
    w("## 5. 関係")
    w("")
    ids_here = {r[0] for r in here}
    rows = con.execute(
        "SELECT t0, t1, a, b, kind, level FROM bond "
        "WHERE t0_k <= ? AND (t1_k IS NULL OR t1_k >= ?) ORDER BY t0_k", (hi, lo)).fetchall()
    rows = [r for r in rows if not ids_here or r[2] in ids_here or r[3] in ids_here]
    if rows:
        w("| 人物A | 人物B | 関係 | 強度 | いつから |")
        w("| --- | --- | --- | --- | --- |")
        for t0, t1, a, b, kind, level in rows:
            w(f"| {a} | {b} | {kind} | {trim(level)} | {t0}{'〜' + t1 if t1 else ''} |")
    else:
        w("台帳にまだない。")
    w("")

    # 6. 火種
    w("## 6. 張っている火種")
    w("")
    w("<!-- 値が高いほど、次に何か起きる。限界の欄がそのまま次の一手の候補になる -->")
    rows = con.execute(
        "SELECT id, t0, name, axis, level, edge, place, star FROM tension "
        "WHERE t0_k <= ? AND (star = ? OR star = '') ORDER BY t0_k", (hi, star)).fetchall()
    cur = {}
    for tid, t0, name, axis, level, edge, pid, st in rows:
        if in_scope(pid):
            prev = cur.get(tid)
            cur[tid] = (level, name, axis, edge, t0, pid, prev[0] if prev else None)
    if cur:
        w("| 火種 | 値 | 前 | 対立軸 | 限界で起きること | 場所 |")
        w("| --- | --- | --- | --- | --- | --- |")
        for tid, (level, name, axis, edge, t0, pid, prev) in sorted(
                cur.items(), key=lambda kv: -(kv[1][0] or 0)):
            arrow = "—" if prev is None else trim(prev)
            w(f"| {name or tid} | {trim(level)}（{t0}） | {arrow} | {axis or '—'} "
              f"| {edge or '—'} | {pid or '—'} |")
    else:
        w("台帳にまだない。")
    w("")

    # 7. 他の星
    others = [s for s in cfg.get("星", {}) if s != star]
    if others:
        w("## 7. 他の星から届いている信号")
        w("")
        w("<!-- 届くのは信号であって、意味ではない。読める者がいるかは別の話 -->")
        w("")
        for other in others:
            d = delay_between(cfg, star, other)
            if d is None:
                w(f"### {other}（遅れの設定なし。全部見える扱い）")
                cut = hi
            else:
                cut = stamp_key(year_of(hi) - d, end=True)
                w(f"### {other}（光の遅れ {d} 年。{year_of(cut)} 年までの出来事しか届かない）")
            w("")
            rows = con.execute(
                f"SELECT {ev_cols} FROM event WHERE star = ? AND t0_k <= ? AND t0_k >= ? "
                "ORDER BY t0_k DESC", (other, cut, span_key(cut, span))).fetchall()
            w(event_table(rows, lambda pid: True, lambda pid: False, visible) or "この射程には届いていない。")
            w("")

    # 8. 秘匿
    rows = con.execute(
        f"SELECT {ev_cols} FROM event WHERE t0_k <= ? ORDER BY t0_k DESC", (hi,)).fetchall()
    hidden = [r for r in rows if (r[7] or "公然") not in ("公然", star)]
    if hidden:
        w("## 8. この星からは見えないこと")
        w("")
        if full:
            w("<!-- 作者だけが知っている。本文にこの語を一つも出さない -->")
            w(event_table(hidden, lambda pid: True, lambda pid: False, lambda o: True))
        else:
            w(f"この時点で {len(hidden)} 件ある。`--full` で出る。"
              "**本文を書くあいだは見ないほうがいい**（住人が知らないことを書いてしまう）。")
        w("")

    print("\n".join(out))


def trim(v):
    if v is None:
        return "—"
    return str(int(v)) if float(v).is_integer() else str(v)


def event_table(rows, in_scope, wide, visible):
    body = []
    for eid, t0, t1, star, pid, kind, scale, open_, summary, actors, ref in rows:
        if not in_scope(pid):
            continue
        if not visible(open_):
            continue
        when = t0 + (f"〜{t1}" if t1 else "")
        mark = "（広域）" if wide(pid) else ""
        body.append(f"| {when} | {kind or '—'} | {trim(scale)} | {pid or '—'}{mark} "
                    f"| {summary} | {actors or '—'} | {ref or eid} |")
    if not body:
        return ""
    head = ["| 年 | 種別 | 規模 | 場所 | 出来事 | 関与 | 出典 |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    return "\n".join(head + body)


# --------------------------------------------------------------------- 系列

def series(world, metric, star=None, place=None):
    cfg = load_config(world)
    con = connect(world)
    star = resolve_star(cfg, star)
    sql = "SELECT t0, star, place, value, unit, ref FROM metric WHERE name = ?"
    args = [metric]
    if star:
        sql += " AND (star = ? OR star = '')"
        args.append(star)
    if place:
        sql += " AND place = ?"
        args.append(place)
    rows = con.execute(sql + " ORDER BY t0_k", args).fetchall()
    if not rows:
        raise SystemExit(f"その指標の記録がない: {metric}")
    print(f"# {metric} / {world}")
    print()
    print("| 年 | 星 | 場所 | 値 | 単位 | 前回比 | 出典 |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    prev = None
    for t0, st, pid, value, unit, ref in rows:
        if prev is None:
            diff = "—"
        elif prev == 0:
            diff = "—"
        else:
            diff = f"{(value - prev) / abs(prev) * 100:+.0f}%"
        print(f"| {t0} | {st or '—'} | {pid or '—'} | {trim(value)} | {unit or '—'} | {diff} | {ref or '—'} |")
        prev = value


# --------------------------------------------------------------------- 追記

def add(world, table, sets, no_build=False):
    if table not in SCHEMAS:
        raise SystemExit(f"そんな台帳はない: {table}（{', '.join(SCHEMAS)}）")
    sc = SCHEMAS[table]
    wdir = world_dir(world)
    path = os.path.join(wdir, RECORDS, sc.file)
    if not os.path.exists(path):
        raise SystemExit(f"台帳がない: {os.path.relpath(path, ROOT)}")

    values = {}
    for pair in sets:
        if "=" not in pair:
            raise SystemExit(f"--set は 列=値 の形で書く: {pair}")
        k, v = pair.split("=", 1)
        k = k.strip()
        if k not in sc.by_md:
            raise SystemExit(f"{table} にその列はない: {k}（{', '.join(c.md for c in sc.cols)}）")
        values[k] = v.strip()

    tables = [t for t in read_tables(path) if {c.md for c in sc.cols if c.req}.issubset(set(t[0]))]
    if not tables:
        raise SystemExit(f"{os.path.relpath(path, ROOT)} に {table} の表が見つからない")
    header, body, end = tables[-1]

    if sc.key:
        key_md = next(c.md for c in sc.cols if c.db == sc.key)
        if not values.get(key_md):
            values[key_md] = next_id(path, sc, key_md, table)

    for c in sc.cols:
        if c.req and not values.get(c.md):
            raise SystemExit(f"必須の列が空: {c.md}")

    cells = [values.get(h, "").replace("|", "\\|") for h in header]
    line = "| " + " | ".join(cells) + " |"

    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    at = body[-1][0] if body else end
    lines.insert(at, line + "\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    print(f"足した: {os.path.relpath(path, ROOT)}:{at + 1}")
    print(f"  {line}")
    if not no_build:
        build(world, quiet=True)
        print("  DB を組み直した")


def next_id(path, sc, key_md, table):
    prefix = {"place": "pl", "actor": "ac", "event": "ev", "act": "dd", "tension": "ts"}.get(table, table[:2])
    top = 0
    for header, body, _ in read_tables(path):
        if key_md not in header:
            continue
        idx = header.index(key_md)
        for _, cells in body:
            if idx < len(cells):
                m = re.match(rf"{prefix}-(\d+)$", cells[idx])
                if m:
                    top = max(top, int(m.group(1)))
    return f"{prefix}-{top + 1:04d}"


# --------------------------------------------------------------------- 本体

def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--world", default=None, help="宇宙名（worlds/ 直下のディレクトリ）")

    p = argparse.ArgumentParser(description="世界の記録（年代記）", parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_cmd(name, help_):
        return sub.add_parser(name, help=help_, parents=[common])

    add_cmd("build", "台帳から DB を組み上げる")
    add_cmd("check", "台帳の矛盾を探す")

    b = add_cmd("brief", "ある時点の断面を出す")
    b.add_argument("--star", help="星名")
    b.add_argument("--year", help="西暦。4360 / 4360-07 / 4360-07-12")
    b.add_argument("--place", help="場所 id か名。その内側と外側を含める")
    b.add_argument("--span", type=int, help="何年さかのぼるか")
    b.add_argument("--full", action="store_true", help="秘匿もふくめて出す（作者の目）")

    s = add_cmd("series", "指標の推移を出す")
    s.add_argument("--metric", required=True)
    s.add_argument("--star")
    s.add_argument("--place")

    a = add_cmd("add", "台帳に一行足す")
    a.add_argument("--table", required=True, help=" / ".join(SCHEMAS))
    a.add_argument("--set", action="append", default=[], metavar="列=値")
    a.add_argument("--no-build", action="store_true")

    q = add_cmd("sql", "DB に直接問い合わせる")
    q.add_argument("query")

    add_cmd("worlds", "宇宙の一覧")

    args = p.parse_args()

    if args.cmd == "worlds":
        for name in sorted(os.listdir(WORLDS_DIR)):
            if os.path.isdir(os.path.join(WORLDS_DIR, name)):
                mark = "記録あり" if os.path.isdir(os.path.join(WORLDS_DIR, name, RECORDS)) else "記録なし"
                print(f"{name}\t{mark}")
        return

    world = args.world or only_world()

    if args.cmd == "build":
        build(world)
    elif args.cmd == "check":
        sys.exit(check(world))
    elif args.cmd == "brief":
        brief(world, args.star, args.year, args.place, args.span, args.full)
    elif args.cmd == "series":
        series(world, args.metric, args.star, args.place)
    elif args.cmd == "add":
        add(world, args.table, args.set, args.no_build)
    elif args.cmd == "sql":
        con = connect(world)
        cur = con.execute(args.query)
        if cur.description:
            print("\t".join(c[0] for c in cur.description))
            for row in cur.fetchall():
                print("\t".join("" if v is None else str(v) for v in row))


def only_world():
    found = [n for n in sorted(os.listdir(WORLDS_DIR))
             if os.path.isdir(os.path.join(WORLDS_DIR, n, RECORDS))]
    if len(found) == 1:
        return found[0]
    raise SystemExit(f"--world を指定すること（記録のある宇宙: {', '.join(found) or 'なし'}）")


if __name__ == "__main__":
    main()
