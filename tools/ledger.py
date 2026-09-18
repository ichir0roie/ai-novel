#!/usr/bin/env python3
"""マークダウンの台帳を読み、DB へ取り込む。書き戻しもここ。

表の形は `schema.py` が決めている。このファイルは**運ぶだけ**。

    from ledger import build_world, read_world

読み方と使いどころは core/chronicle.md。
"""
import json
import os
import re

from sqlalchemy.orm import Session

import schema
from schema import LEDGERS, NUM, STAMP, by_header, headers, md_cols

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLDS_DIR = os.path.join(ROOT, "worlds")
RECORDS = "records"
DB_NAME = "world.db"

DEFAULT_CFG = {"現在": None, "星": {}, "光の遅れ": [], "既定の射程": 60}


# ------------------------------------------------------------------ 年（時刻）

STAMP_RE = re.compile(r"(-?\d{1,5})(?:[-/](\d{1,2}))?(?:[-/](\d{1,2}))?")


def stamp_key(raw, end=False):
    """「4360」「4360-07」「4360-07-12」「3150 年ごろ」→ 並べ替え用の整数。

    end=True のときは、省かれた月日を年末・月末で埋める（範囲の上限用）。
    読めなければ None。
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    m = STAMP_RE.search(text)
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else (12 if end else 0)
    day = int(m.group(3)) if m.group(3) else (31 if end else 0)
    return year * 10000 + month * 100 + day


def year_of(key):
    return None if key is None else key // 10000


def back_years(key, years):
    return key - years * 10000


def to_num(raw):
    """「1,000」「-2」「80 %」から数だけ拾う。拾えなければ None。"""
    if raw is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(raw).replace(",", ""))
    return float(m.group(0)) if m else None


# ------------------------------------------------------- マークダウンの表を読む

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
    """ファイル中のマークダウン表を全部返す。[(見出し, [(行番号, セル)], 表の最終行)]"""
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
            head = split_row(block[0][1])
            body = []
            for lineno, raw in block[1:]:
                cells = split_row(raw)
                if cells and all(SEP_CELL.match(c) for c in cells if c):
                    continue
                body.append((lineno, cells))
            out.append((head, body, block[-1][0]))
        block = []
    return out


def ledger_path(wdir, model):
    return os.path.join(wdir, RECORDS, model.md_file)


def parse_ledger(wdir, model):
    """台帳を読んで、行の辞書と、気づいたことを返す。

    **見出しがスキーマと一致する表だけ**を台帳として扱う。
    一致しない表は読み飛ばし、その旨を notes に残す（typo を見逃さないため）。
    """
    path = ledger_path(wdir, model)
    rel = os.path.relpath(path, ROOT)
    want = headers(model)
    cols = by_header(model)
    rows, notes = [], []

    if not os.path.exists(path):
        return rows, [("警告", rel, f"{model.ja}の台帳がない。空として扱う")]

    found = 0
    for head, body, _ in read_tables(path):
        if set(head) != set(want):
            missing = [h for h in want if h not in head]
            extra = [h for h in head if h not in want]
            if missing and len(missing) == len(want):
                continue  # 台帳とは無関係の表。触らない
            notes.append(("エラー", rel,
                          f"{model.ja}の表として読めない表がある"
                          + (f"／足りない列: {'、'.join(missing)}" if missing else "")
                          + (f"／知らない列: {'、'.join(extra)}" if extra else "")))
            continue
        found += 1
        for lineno, cells in body:
            if len(cells) < len(head):
                cells += [""] * (len(head) - len(cells))
            rec = {"src": f"{rel}:{lineno}"}
            for header, value in zip(head, cells):
                col = cols.get(header)
                if col is not None:
                    rec[col.name] = value
            if not any(rec.get(c.name, "") for c in md_cols(model)):
                continue
            rows.append(rec)
    if not found:
        notes.append(("エラー", rel,
                      f"{model.ja}の表が一つも見つからない。"
                      f"見出しはこの形でなければならない: | {' | '.join(want)} |"))
    return rows, notes


def apply_inherit(model, rows):
    """火種のように、同じ id の二行目以降で定義列を省けるようにする。"""
    if not (model.inherit and model.key_col):
        return
    first = {}
    for rec in rows:
        rid = rec.get(model.key_col, "")
        if rid not in first:
            first[rid] = rec
            continue
        for name in model.inherit:
            if not rec.get(name):
                rec[name] = first[rid].get(name, "")


def read_world(wdir):
    """全台帳を読む。{テーブル名: [行]} と気づいたこと。DB には触らない。"""
    data, notes = {}, []
    for model in LEDGERS:
        rows, note = parse_ledger(wdir, model)
        apply_inherit(model, rows)
        data[model.__tablename__] = rows
        notes += note
    return data, notes


# ------------------------------------------------------------------- 取り込み

def to_instance(model, rec):
    """マークダウンの一行を、DB に入れられる形にする。"""
    values = {"src": rec.get("src", "")}
    for col in md_cols(model):
        raw = rec.get(col.name, "")
        kind = col.info.get("kind")
        if kind == NUM:
            values[col.name] = to_num(raw)
        else:
            values[col.name] = raw
        if kind == STAMP:
            values[f"{col.name}_k"] = stamp_key(raw)
    return model(**values)


def build_world(world, quiet=False):
    """**台帳 → db ファイル。** 作り直して、全行を入れる。"""
    wdir = world_dir(world)
    data, notes = read_world(wdir)
    db_path = os.path.join(wdir, DB_NAME)
    engine = schema.create_db(db_path)

    counts = {}
    with Session(engine) as session:
        for model in LEDGERS:
            rows = data[model.__tablename__]
            session.add_all([to_instance(model, rec) for rec in rows])
            counts[model.__tablename__] = len(rows)
        session.commit()

    if not quiet:
        print(f"組み上げた: {os.path.relpath(db_path, ROOT)}")
        print("  " + "  ".join(f"{t}={n}" for t, n in counts.items()))
        for level, where, msg in notes:
            print(f"  {level} {where}: {msg}")
    return engine, counts, notes


# --------------------------------------------------------------------- 書き戻し

def next_id(wdir, model):
    """`ev-0043` のような id を、いまある最大の次に振る。"""
    path = ledger_path(wdir, model)
    key_md = next(c.info["md"] for c in md_cols(model) if c.name == model.key_col)
    top = 0
    for head, body, _ in read_tables(path):
        if key_md not in head:
            continue
        at = head.index(key_md)
        for _, cells in body:
            if at < len(cells):
                m = re.match(rf"{model.id_prefix}-(\d+)$", cells[at])
                if m:
                    top = max(top, int(m.group(1)))
    return f"{model.id_prefix}-{top + 1:04d}"


def append_row(wdir, model, values):
    """台帳の**最後の表**に一行足す。値はマークダウンの見出しをキーにした辞書。"""
    path = ledger_path(wdir, model)
    if not os.path.exists(path):
        raise FileNotFoundError(os.path.relpath(path, ROOT))

    want = headers(model)
    tables = [t for t in read_tables(path) if set(t[0]) == set(want)]
    if not tables:
        raise LookupError(f"{os.path.relpath(path, ROOT)} に{model.ja}の表がない")
    head, body, end = tables[-1]

    cells = [str(values.get(h, "")).replace("|", "\\|") for h in head]
    line = "| " + " | ".join(cells) + " |"

    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    at = body[-1][0] if body else end
    lines.insert(at, line + "\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    return os.path.relpath(path, ROOT), at + 1, line


def blank_ledger(model):
    """空の台帳のマークダウン。`init` が使う。**表の形はスキーマから作る。**"""
    head = headers(model)
    return "\n".join([
        f"# {model.ja}",
        "",
        f"<!-- chronicle: {model.__tablename__}。{model.about} -->",
        "<!-- 列の形は tools/schema.py が決めている。勝手に足さない -->",
        "",
        "| " + " | ".join(head) + " |",
        "| " + " | ".join("---" for _ in head) + " |",
        "",
    ])


# ----------------------------------------------------------------------- 宇宙

def world_dir(world):
    path = os.path.join(WORLDS_DIR, world)
    if not os.path.isdir(path):
        raise SystemExit(f"そんな宇宙はない: {world}（{os.path.relpath(WORLDS_DIR, ROOT)} を見よ）")
    return path


def db_path(world):
    return os.path.join(world_dir(world), DB_NAME)


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


def known_worlds():
    if not os.path.isdir(WORLDS_DIR):
        return []
    return [n for n in sorted(os.listdir(WORLDS_DIR))
            if os.path.isdir(os.path.join(WORLDS_DIR, n, RECORDS))]


def only_world():
    found = known_worlds()
    if len(found) == 1:
        return found[0]
    raise SystemExit(f"--world を指定すること（記録のある宇宙: {'、'.join(found) or 'なし'}）")
