#!/usr/bin/env python3
"""世界の記録（年代記）。

マークダウンの台帳を SQLite に組み上げ、任意の時点の「断面」を取り出す。

    python3 tools/chronicle.py init   --world <宇宙>        台帳の雛形を作る
    python3 tools/chronicle.py build  --world <宇宙>        台帳 → world.db
    python3 tools/chronicle.py check  --world <宇宙>        矛盾を探す
    python3 tools/chronicle.py brief  --star 入植星 --year 4360 --place mushvan-land
    python3 tools/chronicle.py series --metric 人口
    python3 tools/chronicle.py add    --table event --set 年=4361 --set 出来事=...
    python3 tools/chronicle.py sql    "select * from event limit 5"
    python3 tools/chronicle.py schema                        台帳の形を表示

表の形は tools/schema.py（SQLAlchemy）が決めている。
台帳の原本は worlds/<宇宙>/records/*.md。DB は組み上げ直せるので git に入れない。
読み方と使いどころは core/chronicle.md。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select                                    # noqa: E402
from sqlalchemy.orm import Session                               # noqa: E402

import ledger                                                    # noqa: E402
import schema                                                    # noqa: E402
from ledger import (ROOT, back_years, db_path, delay_between,    # noqa: E402
                    load_config, resolve_star, stamp_key, world_dir, year_of)
from schema import (ENTRIES, ENTRY_KEY, LEDGERS, TABLES, Act,   # noqa: E402
                    Actor, Bond, Concept, Event, Metric, Place,
                    Tension, Term, Thing, headers, md_cols)


# ----------------------------------------------------------------------- 検査

def check(world):
    wdir = world_dir(world)
    cfg = load_config(world)
    data, notes = ledger.read_world(wdir)

    ids = {m.__tablename__: {r.get(m.key_col, "") for r in data[m.__tablename__]}
           for m in LEDGERS if m.key_col}
    errors = [f"{where}: {msg}" for level, where, msg in notes if level == "エラー"]
    warns = [f"{where}: {msg}" for level, where, msg in notes if level != "エラー"]

    for model in LEDGERS:
        name, seen_key, seen_uniq = model.ja, {}, {}
        for rec in data[model.__tablename__]:
            at = rec.get("src", "?")
            for col in md_cols(model):
                value = rec.get(col.name, "")
                info = col.info
                if info["req"] and not value:
                    errors.append(f"{at} [{name}] 必須の「{info['md']}」が空")
                if info["kind"] == schema.STAMP and value and stamp_key(value) is None:
                    errors.append(f"{at} [{name}] 「{info['md']}」の年が読めない: {value}")
                if info["kind"] == schema.NUM and value and ledger.to_num(value) is None:
                    errors.append(f"{at} [{name}] 「{info['md']}」の値が数ではない: {value}")
                if info["ref"] and value:
                    for one in filter(None, __import__("re").split(r"[,、/ ]+", value)):
                        if one not in ids.get(info["ref"], set()):
                            warns.append(f"{at} [{name}] 「{info['md']}」の {one} が"
                                         f" {schema.find(info['ref']).ja}台帳にない")

            # 同じ id を年ちがいで並べる台帳（火種）は、id の重複が正しい
            if model.key_col and not model.uniq:
                rid = rec.get(model.key_col, "")
                if rid in seen_key:
                    errors.append(f"{at} [{name}] id が重複: {rid}（初出 {seen_key[rid]}）")
                else:
                    seen_key[rid] = at
            if model.uniq:
                tup = tuple(rec.get(c, "") for c in model.uniq)
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
                warns.append(f"{at} [{name}] config.json にない星: {star}")

    parent = {r.get("id"): r.get("parent", "") for r in data["place"]}
    for pid in parent:
        seen, cur = {pid}, parent.get(pid, "")
        while cur:
            if cur in seen:
                errors.append(f"[場所] 親が輪になっている: {pid}")
                break
            seen.add(cur)
            cur = parent.get(cur, "")

    for line in warns:
        print(f"警告 {line}")
    for line in errors:
        print(f"エラー {line}")
    print(f"--- エラー {len(errors)} 件 / 警告 {len(warns)} 件")
    return 1 if errors else 0


# ----------------------------------------------------------------------- 断面

def session_for(world):
    path = db_path(world)
    if not os.path.exists(path):
        ledger.build_world(world, quiet=True)
    return Session(schema.open_db(path))


def place_scope(session, place):
    """その場所と、内側（子孫）と、外側（先祖）の id を返す。"""
    rows = session.execute(select(Place.id, Place.name, Place.parent)).all()
    parent = {r.id: r.parent for r in rows}
    if place not in parent:
        for r in rows:
            if r.name == place:
                place = r.id
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


def trim(v):
    if v is None:
        return "—"
    return str(int(v)) if float(v).is_integer() else str(v)


def event_table(rows, in_scope, wide, visible):
    body = []
    for e in rows:
        if not in_scope(e.place) or not visible(e.visibility):
            continue
        when = e.t0 + (f"〜{e.t1}" if e.t1 else "")
        mark = "（広域）" if wide(e.place) else ""
        body.append(f"| {when} | {e.kind or '—'} | {trim(e.scale)} | {e.place or '—'}{mark} "
                    f"| {e.summary} | {e.actors or '—'} | {e.ref or e.id} |")
    if not body:
        return ""
    return "\n".join(["| 年 | 種別 | 規模 | 場所 | 出来事 | 関与 | 出典 |",
                      "| --- | --- | --- | --- | --- | --- | --- |"] + body)


def brief(world, star, year, place=None, span=None, full=False):
    cfg = load_config(world)
    star = resolve_star(cfg, star)
    year = year or cfg.get("現在")
    if year is None:
        raise SystemExit("--year を指定するか、config.json に「現在」を書くこと")
    lo, hi = stamp_key(year), stamp_key(year, end=True)
    if lo is None:
        raise SystemExit(f"年が読めない: {year}")
    span = span or cfg.get("既定の射程", 60)
    back = back_years(lo, span)

    out = []
    w = out.append

    with session_for(world) as session:
        inner = outer = None
        place_id = place
        if place:
            inner, outer, place_id = place_scope(session, place)
            if inner is None:
                w(f"<!-- 場所 {place} が台帳にない。星全体で出す -->")

        def in_scope(pid):
            if not pid or inner is None:
                return True
            return pid in inner or pid in outer

        def wide(pid):
            return bool(outer) and pid in outer

        def visible(v):
            """公開列は「誰から見えるか」。公然=全員 / 秘匿=誰も / 星名=その星だけ。"""
            return True if full else (v or "公然") in ("公然", star)

        def mine(model):
            return (model.star == star) | (model.star == "")

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
        rows = session.scalars(select(Metric).where(Metric.t0_k <= hi, mine(Metric))
                               .order_by(Metric.name, Metric.t0_k)).all()
        latest = {}
        for m in rows:
            if not in_scope(m.place):
                continue
            key = (m.name, m.place)
            latest[key] = (m, latest.get(key, (None,))[0])
        if latest:
            w("| 指標 | 値 | 前回 | 動き | 場所 | 出典 |")
            w("| --- | --- | --- | --- | --- | --- |")
            for (name, pid), (cur, prev) in sorted(latest.items()):
                shown = f"{trim(cur.value)} {cur.unit}".strip()
                if prev is not None:
                    move = "増" if cur.value > prev.value else ("減" if cur.value < prev.value else "横ばい")
                    past = f"{trim(prev.value)}（{prev.t0}）"
                else:
                    move, past = "—", "—"
                w(f"| {name} | {shown}（{cur.t0}） | {past} | {move} | {pid or '—'} | {cur.ref or '—'} |")
        else:
            w("記録なし。")
        w("")

        # 2. 続いている出来事
        w("## 2. 続いている出来事")
        w("")
        w("<!-- この時点で始まっていて、まだ終わっていないもの -->")
        rows = session.scalars(
            select(Event).where(Event.t0_k <= hi, Event.t1_k.is_not(None), Event.t1_k >= lo,
                                mine(Event)).order_by(Event.t0_k)).all()
        w(event_table(rows, in_scope, wide, visible) or "なし。")
        w("")

        # 3. 直近の出来事
        w(f"## 3. 直近の出来事（{year_of(back)}〜{year_of(hi)}）")
        w("")
        rows = session.scalars(
            select(Event).where(Event.t0_k <= hi, Event.t0_k >= back, mine(Event))
            .order_by(Event.t0_k.desc())).all()
        w(event_table(rows, in_scope, wide, visible) or "なし。")
        w("")

        # 3.5 この射程で誰が何をしたか
        rows = session.scalars(
            select(Act).where(Act.t0_k <= hi, Act.t0_k >= back).order_by(Act.t0_k.desc())).all()
        rows = [a for a in rows if in_scope(a.place) and visible(a.visibility)]
        if rows:
            w("## 3.5 この射程での行動")
            w("")
            w("<!-- 代償の欄が、次の話で誰が何を失ったままかを示す -->")
            w("| 年 | 人物 | 行動 | 動機 | 代償 | 結果 |")
            w("| --- | --- | --- | --- | --- | --- |")
            for a in rows:
                w(f"| {a.t0} | {a.actor} | {a.deed} | {a.motive or '—'} "
                  f"| {a.cost or '—'} | {a.result or '—'} |")
            w("")

        # 4. その場にいる者
        w("## 4. その場にいる者")
        w("")
        rows = session.scalars(
            select(Actor).where((Actor.born_k.is_(None)) | (Actor.born_k <= hi),
                                (Actor.died_k.is_(None)) | (Actor.died_k >= lo),
                                mine(Actor)).order_by(Actor.id)).all()
        here = [a for a in rows if in_scope(a.place)]
        if here:
            w("<!-- 詳しくは右のファイルを読む。`chronicle.py entry <id>` でも引ける -->")
            w("| id | 名 | 種別 | 系統 | 齢／いつから | 居所 | 一言 | ファイル |")
            w("| --- | --- | --- | --- | --- | --- | --- | --- |")
            for a in here:
                if not a.born_k:
                    age = "—"
                elif a.kind == "個人":
                    age = f"{year_of(hi) - year_of(a.born_k)} 歳"
                else:
                    age = f"{year_of(a.born_k)} 年〜"
                w(f"| {a.id} | {a.name} | {a.kind or '—'} | {a.line or '—'} | {age} "
                  f"| {a.place or '—'} | {a.note or '—'} | `{a.path}` |")
        else:
            w("台帳にまだ誰もいない。")
        w("")

        # 5. 関係
        w("## 5. 関係")
        w("")
        ids_here = {a.id for a in here}
        rows = session.scalars(
            select(Bond).where(Bond.t0_k <= hi, (Bond.t1_k.is_(None)) | (Bond.t1_k >= lo))
            .order_by(Bond.t0_k)).all()
        rows = [b for b in rows if not ids_here or b.a in ids_here or b.b in ids_here]
        if rows:
            w("| 人物A | 人物B | 関係 | 強度 | いつから |")
            w("| --- | --- | --- | --- | --- |")
            for b in rows:
                w(f"| {b.a} | {b.b} | {b.kind} | {trim(b.level)} | {b.t0}{'〜' + b.t1 if b.t1 else ''} |")
        else:
            w("台帳にまだない。")
        w("")

        # 6. 火種
        w("## 6. 張っている火種")
        w("")
        w("<!-- 値が高いほど、次に何か起きる。限界の欄がそのまま次の一手の候補になる -->")
        rows = session.scalars(
            select(Tension).where(Tension.t0_k <= hi, mine(Tension)).order_by(Tension.t0_k)).all()
        cur = {}
        for t in rows:
            if in_scope(t.place):
                cur[t.id] = (t, cur.get(t.id, (None,))[0])
        if cur:
            w("| 火種 | 値 | 前 | 対立軸 | 限界で起きること | 場所 |")
            w("| --- | --- | --- | --- | --- | --- |")
            for tid, (t, prev) in sorted(cur.items(), key=lambda kv: -(kv[1][0].level or 0)):
                was = trim(prev.level) if prev is not None else "—"
                w(f"| {t.name or tid} | {trim(t.level)}（{t.t0}） | {was} | {t.axis or '—'} "
                  f"| {t.edge or '—'} | {t.place or '—'} |")
        else:
            w("台帳にまだない。")
        w("")

        # 6.5 この年に使える語
        rows = session.scalars(
            select(Term).where((Term.born_k.is_(None)) | (Term.born_k <= hi),
                               (Term.died_k.is_(None)) | (Term.died_k >= lo),
                               (Term.star == star) | (Term.star == ""))
            .order_by(Term.kind, Term.id)).all()
        live = [t for t in rows if t.state not in ("設定側", "候補")]
        dead = session.scalars(
            select(Term).where(Term.died_k.is_not(None), Term.died_k < lo,
                               (Term.star == star) | (Term.star == ""))
            .order_by(Term.died_k)).all()
        if live:
            w("## 6.5 この年に使える語")
            w("")
            w("<!-- 本文に出してよい語。ここにない語を作ったら terms/ に足す -->")
            w("| 語 | 読み | 種別 | 表での意味 |")
            w("| --- | --- | --- | --- |")
            for t in live:
                w(f"| {t.name} | {t.read or '—'} | {t.kind or '—'} "
                  f"| {t.face or t.common or '—'} |")
            w("")
            if dead:
                w("**この年にはもう死語**: " + "、".join(f"{t.name}（〜{t.died}）" for t in dead))
                w("")

        # 7. 他の星
        others = [s for s in cfg.get("星", {}) if s != star]
        if others:
            w("## 7. 他の星から届いている信号")
            w("")
            w("<!-- 届くのは信号であって、意味ではない。読める者がいるかは別の話 -->")
            for other in others:
                delay = delay_between(cfg, star, other)
                if delay is None:
                    w(f"### {other}（遅れの設定なし。全部見える扱い）")
                    cut = hi
                else:
                    cut = stamp_key(year_of(hi) - delay, end=True)
                    w(f"### {other}（光の遅れ {delay} 年。{year_of(cut)} 年までの出来事しか届かない）")
                w("")
                rows = session.scalars(
                    select(Event).where(Event.star == other, Event.t0_k <= cut,
                                        Event.t0_k >= back_years(cut, span))
                    .order_by(Event.t0_k.desc())).all()
                w(event_table(rows, lambda pid: True, lambda pid: False, visible)
                  or "この射程には届いていない。")
                w("")

        # 8. この星からは見えないこと
        rows = session.scalars(select(Event).where(Event.t0_k <= hi)
                               .order_by(Event.t0_k.desc())).all()
        hidden = [e for e in rows if (e.visibility or "公然") not in ("公然", star)]
        if hidden:
            w("## 8. この星からは見えないこと")
            w("")
            if full:
                w("<!-- 作者だけが知っている。本文にこの語を一つも出さない -->")
                w(event_table(hidden, lambda pid: True, lambda pid: False, lambda v: True))
            else:
                w(f"この時点で {len(hidden)} 件ある。`--full` で出る。"
                  "**本文を書くあいだは見ないほうがいい**（住人が知らないことを書いてしまう）。")
            w("")

    print("\n".join(out))


# ----------------------------------------------------------------------- 系列

def series(world, metric, star=None, place=None):
    cfg = load_config(world)
    star = resolve_star(cfg, star)
    with session_for(world) as session:
        stmt = select(Metric).where(Metric.name == metric)
        if star:
            stmt = stmt.where((Metric.star == star) | (Metric.star == ""))
        if place:
            stmt = stmt.where(Metric.place == place)
        rows = session.scalars(stmt.order_by(Metric.t0_k)).all()
        if not rows:
            raise SystemExit(f"その指標の記録がない: {metric}")
        print(f"# {metric} / {world}")
        print()
        print("| 年 | 星 | 場所 | 値 | 単位 | 前回比 | 出典 |")
        print("| --- | --- | --- | --- | --- | --- | --- |")
        prev = None
        for m in rows:
            diff = "—" if prev in (None, 0) else f"{(m.value - prev) / abs(prev) * 100:+.0f}%"
            print(f"| {m.t0} | {m.star or '—'} | {m.place or '—'} | {trim(m.value)} "
                  f"| {m.unit or '—'} | {diff} | {m.ref or '—'} |")
            prev = m.value


# ----------------------------------------------------------------------- 追記

def add(world, table, sets, no_build=False):
    try:
        model = schema.find(table)
    except KeyError:
        raise SystemExit(f"そんな台帳はない: {table}"
                         f"（{'、'.join(m.__tablename__ for m in TABLES)}）")
    if model.source == "entry":
        raise SystemExit(
            f"{model.ja}は 1 ファイル 1 レコード。add では足せない。\n"
            f"  1. python3 tools/chronicle.py template --kind {model.entry_kind}\n"
            f"  2. 出てきた雛形を {model.dir_hint or '好きな場所'} に書く（本文も書く）\n"
            f"  3. python3 tools/chronicle.py build")
    wdir = world_dir(world)
    allowed = headers(model)

    values = {}
    for pair in sets:
        if "=" not in pair:
            raise SystemExit(f"--set は 列=値 の形で書く: {pair}")
        key, value = pair.split("=", 1)
        key = key.strip()
        if key not in allowed:
            raise SystemExit(f"{model.ja}にその列はない: {key}（{'、'.join(allowed)}）")
        values[key] = value.strip()

    if model.key_col:
        key_md = next(c.info["md"] for c in md_cols(model) if c.name == model.key_col)
        if not values.get(key_md):
            values[key_md] = ledger.next_id(wdir, model)

    for col in md_cols(model):
        if col.info["req"] and not values.get(col.info["md"]):
            raise SystemExit(f"必須の列が空: {col.info['md']}")

    rel, lineno, line = ledger.append_row(wdir, model, values)
    print(f"足した: {rel}:{lineno}")
    print(f"  {line}")
    if not no_build:
        ledger.build_world(world, quiet=True)
        print("  DB を組み直した")


# ------------------------------------------------------------------- 雛形作り

def init(world):
    wdir = os.path.join(ledger.WORLDS_DIR, world)
    rdir = os.path.join(wdir, ledger.RECORDS)
    os.makedirs(rdir, exist_ok=True)
    made = []
    for model in TABLES:
        path = os.path.join(rdir, model.md_file)
        if os.path.exists(path):
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(ledger.blank_ledger(model))
        made.append(os.path.relpath(path, ROOT))
    cfg = os.path.join(rdir, "config.json")
    if not os.path.exists(cfg):
        with open(cfg, "w", encoding="utf-8") as fh:
            fh.write('{\n  "宇宙": "%s",\n  "現在": null,\n  "既定の射程": 60,\n'
                     '  "星": {},\n  "光の遅れ": []\n}\n' % world)
        made.append(os.path.relpath(cfg, ROOT))
    for sub_dir in ("stories", "terms", "concepts"):
        os.makedirs(os.path.join(wdir, sub_dir), exist_ok=True)
    if made:
        print("作った:")
        for path in made:
            print(f"  {path}")
    else:
        print("すでに全部ある。")
    print(f"つぎ: {os.path.relpath(cfg, ROOT)} に星と光の遅れを書く")


def template(kind):
    """記事の雛形を出す。**front matter がレコード、その下が文章。**"""
    try:
        model = schema.entry_model(kind)
    except KeyError:
        raise SystemExit(f"知らない記録: {kind}"
                         f"（{'／'.join(m.entry_kind for m in ENTRIES)}）")
    print("---")
    print(f"{ENTRY_KEY}: {model.entry_kind}")
    for col in md_cols(model):
        mark = "" if not col.info["req"] else "      # 必須"
        print(f"{col.info['md']}:{mark}")
    print("---")
    print()
    print(f"# <{model.ja}の名>")
    print()
    print("<ここから下が文章。front matter に入りきらないことを書く。>")
    print("<レコードは front matter、読み物は本文。**同じことを二度書かない**。>")
    print()
    print(f"<!-- 置き場所の目安: worlds/<宇宙>/{model.dir_hint or ''} -->", end="")
    print(f" <!-- {model.about} -->")


def show_entry(world, ident):
    """記事を一件、front matter ごと出す。"""
    with session_for(world) as session:
        for model in ENTRIES:
            hit = session.scalars(
                select(model).where((model.id == ident) | (model.name == ident))).first()
            if hit is None:
                continue
            print(f"# {hit.name}　`{hit.id}`　{model.ja}")
            print()
            print(f"<!-- {hit.path} -->")
            print()
            print("| | |")
            print("| --- | --- |")
            for col in md_cols(model):
                value = getattr(hit, col.name, "")
                if value not in ("", None) and col.name != "name":
                    print(f"| {col.info['md']} | {value} |")
            print()
            print(hit.body or "（本文なし）")
            return
    raise SystemExit(f"その記事がない: {ident}")


def list_entries(world, kind=None, star=None, year=None):
    """記事の一覧。種類・星・年で絞れる。"""
    cfg = load_config(world)
    star = resolve_star(cfg, star)
    models = [schema.entry_model(kind)] if kind else list(ENTRIES)
    lo = hi = None
    if year:
        lo, hi = stamp_key(year), stamp_key(year, end=True)
    with session_for(world) as session:
        for model in models:
            stmt = select(model)
            if star:
                stmt = stmt.where((model.star == star) | (model.star == ""))
            if hi is not None and hasattr(model, "born_k"):
                stmt = stmt.where((model.born_k.is_(None)) | (model.born_k <= hi),
                                  (model.died_k.is_(None)) | (model.died_k >= lo))
            rows = session.scalars(stmt.order_by(model.id)).all()
            if not rows:
                continue
            print(f"## {model.ja}（{len(rows)} 件）")
            print()
            print("| id | 名 | 種別 | 星 | ファイル |")
            print("| --- | --- | --- | --- | --- |")
            for r in rows:
                print(f"| {r.id} | {r.name} | {getattr(r, 'kind', '') or '—'} "
                      f"| {r.star or '—'} | {r.path} |")
            print()


INDEX_START = "<!-- chronicle:index start -->"
INDEX_END = "<!-- chronicle:index end -->"

INDEX_COLS = {
    "actor": ("名", "読み", "種別", "星", "一言"),
    "thing": ("名", "読み", "種別", "星", "一言"),
    "term": ("名", "読み", "種別", "星", "表", "裏", "状態"),
    "concept": ("名", "星", "一言"),
}


def build_index(world):
    """記事の索引を作る。**glossary.md の中身はこれで置き換える。**"""
    out = [INDEX_START, "",
           "<!-- ここは自動生成。手で書かない。"
           "`python3 tools/chronicle.py index` で作り直す -->", ""]
    with session_for(world) as session:
        for model in ENTRIES:
            rows = session.scalars(select(model).order_by(model.star, model.id)).all()
            if not rows:
                continue
            keys = INDEX_COLS[model.__tablename__]
            cols = {c.info["md"]: c.name for c in md_cols(model)}
            out.append(f"## {model.ja}（{len(rows)} 件）")
            out.append("")
            out.append("| " + " | ".join(keys) + " | ファイル |")
            out.append("| " + " | ".join("---" for _ in keys) + " | --- |")
            for r in rows:
                cells = [str(getattr(r, cols[k], "") or "—").replace("|", "\\|") for k in keys]
                out.append("| " + " | ".join(cells) + f" | `{r.path}` |")
            out.append("")
    out.append(INDEX_END)
    return "\n".join(out)


def write_index(world):
    path = os.path.join(world_dir(world), "glossary.md")
    if not os.path.exists(path):
        raise SystemExit(f"{os.path.relpath(path, ROOT)} がない")
    text = open(path, encoding="utf-8").read()
    if INDEX_START not in text or INDEX_END not in text:
        raise SystemExit(f"{os.path.relpath(path, ROOT)} に "
                         f"{INDEX_START} と {INDEX_END} の印がない")
    head = text.split(INDEX_START)[0]
    tail = text.split(INDEX_END, 1)[1]
    open(path, "w", encoding="utf-8").write(head + build_index(world) + tail)
    print(f"索引を作り直した: {os.path.relpath(path, ROOT)}")


def show_schema():
    print("台帳の形。**tools/schema.py が決めている。**")
    print()
    print("入れ物は二種類ある。")
    print()
    print("| | 何で書くか | 何を入れるか |")
    print("| --- | --- | --- |")
    print("| 表 | `records/*.md` の表。一行 = 一レコード | 行が短くて数が多いもの |")
    print("| 記事 | **1 ファイル = 1 レコード。** front matter ＋ 本文 | 文章のつくもの |")
    print()
    for group, title, note in (
            (TABLES, "表", "**列見出しがこれと一致していること。** 食い違う表は取り込まれず、`check` が止める"),
            (ENTRIES, "記事", f"front matter の `{ENTRY_KEY}:` でどの台帳に入るかが決まる。**置き場所は問わない**")):
        print(f"# {title}")
        print()
        print(note)
        print()
        for model in group:
            where = (f"`records/{model.md_file}`" if model.md_file
                     else f"`{ENTRY_KEY}: {model.entry_kind}`　置き場所の目安 `{model.dir_hint}`")
            print(f"## {model.ja}　`{model.__tablename__}`　{where}")
            print()
            print(f"{model.about}")
            print()
            print(f"| {'列' if model.source == 'table' else 'キー'} | 種類 | 必須 | 参照 |")
            print("| --- | --- | --- | --- |")
            for col in md_cols(model):
                info = col.info
                print(f"| {info['md']} | {info['kind']} | {'○' if info['req'] else ''} "
                      f"| {schema.find(info['ref']).ja if info['ref'] else ''} |")
            print()


# ------------------------------------------------------------------------ 本体

def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--world", default=None, help="宇宙名（worlds/ 直下のディレクトリ）")

    p = argparse.ArgumentParser(description="世界の記録（年代記）", parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    def cmd(name, help_):
        return sub.add_parser(name, help=help_, parents=[common])

    cmd("init", "新しい宇宙に台帳の雛形を作る")
    cmd("build", "台帳から world.db を組み上げる")
    cmd("check", "台帳の矛盾を探す")

    b = cmd("brief", "ある時点の断面を出す")
    b.add_argument("--star", help="星名")
    b.add_argument("--year", help="西暦。4360 / 4360-07 / 4360-07-12")
    b.add_argument("--place", help="場所 id か名。その内側と外側を含める")
    b.add_argument("--span", type=int, help="何年さかのぼるか")
    b.add_argument("--full", action="store_true", help="秘匿もふくめて出す（作者の目）")

    s = cmd("series", "指標の推移を出す")
    s.add_argument("--metric", required=True)
    s.add_argument("--star")
    s.add_argument("--place")

    a = cmd("add", "台帳に一行足す")
    a.add_argument("--table", required=True, help="、".join(m.__tablename__ for m in TABLES))
    a.add_argument("--set", action="append", default=[], metavar="列=値")
    a.add_argument("--no-build", action="store_true")

    q = cmd("sql", "DB に直接問い合わせる")
    q.add_argument("query")

    t = cmd("template", "記事（1 ファイル 1 レコード）の雛形を出す")
    t.add_argument("--kind", required=True, help="／".join(m.entry_kind for m in ENTRIES))

    e = cmd("entry", "記事を一件読む")
    e.add_argument("ident", help="id か名")

    ls = cmd("list", "記事の一覧")
    ls.add_argument("--kind", help="／".join(m.entry_kind for m in ENTRIES))
    ls.add_argument("--star")
    ls.add_argument("--year", help="その年に存在していたものだけ")

    cmd("index", "記事の索引を glossary.md に書き出す")
    cmd("worlds", "宇宙の一覧")
    cmd("schema", "台帳の形を表示する")

    args = p.parse_args()

    if args.cmd == "schema":
        return show_schema()
    if args.cmd == "template":
        return template(args.kind)
    if args.cmd == "worlds":
        for name in sorted(os.listdir(ledger.WORLDS_DIR)):
            if not os.path.isdir(os.path.join(ledger.WORLDS_DIR, name)):
                continue
            has = os.path.isdir(os.path.join(ledger.WORLDS_DIR, name, ledger.RECORDS))
            print(f"{name}\t{'記録あり' if has else '記録なし'}")
        return
    if args.cmd == "init":
        if not args.world:
            raise SystemExit("init には --world が要る")
        return init(args.world)

    world = args.world or ledger.only_world()

    if args.cmd == "build":
        ledger.build_world(world)
    elif args.cmd == "check":
        sys.exit(check(world))
    elif args.cmd == "brief":
        brief(world, args.star, args.year, args.place, args.span, args.full)
    elif args.cmd == "series":
        series(world, args.metric, args.star, args.place)
    elif args.cmd == "add":
        add(world, args.table, args.set, args.no_build)
    elif args.cmd == "entry":
        show_entry(world, args.ident)
    elif args.cmd == "list":
        list_entries(world, args.kind, args.star, args.year)
    elif args.cmd == "index":
        write_index(world)
    elif args.cmd == "sql":
        with session_for(world) as session:
            result = session.execute(__import__("sqlalchemy").text(args.query))
            if result.returns_rows:
                print("\t".join(result.keys()))
                for row in result:
                    print("\t".join("" if v is None else str(v) for v in row))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # `| head` などで切られたとき。os._exit で後始末の書き出しを止める
        os._exit(0)
    except KeyboardInterrupt:
        os._exit(130)
