#!/usr/bin/env python3
"""台帳ツールの入口。`novels/` のマークダウンを読んで、組む・検める・断面を出す。

```
python3 tools/novel.py check                 不備を探す。あればコード 1 で止まる
python3 tools/novel.py load                  **作業開始時。** md を db へ読み込む
python3 tools/novel.py save                  **作業終了時。** db を md へ書き出す
python3 tools/novel.py stories --work めぐる旅路は枯れゆく世界と
python3 tools/novel.py read stories/<作品>/episodes/001.md
python3 tools/novel.py write stories/<作品>/episodes/003.md --file 下書き.md
python3 tools/novel.py brief --place ムシュヴァン --time 4360
python3 tools/novel.py list --kind 語 --world SFファンタジー
python3 tools/novel.py show 采配
python3 tools/novel.py template --kind 人物
python3 tools/novel.py index --world SFファンタジー
python3 tools/novel.py sql "SELECT name FROM event WHERE kind LIKE '火種%'"
```

**`novels/` のマークダウンは直に開かない。** 読むのも書くのも、この入口を通す。
形は `tools/schema.py` が一か所で決めている。読み方は `tools/reader.py`。
"""
from __future__ import annotations

import argparse
import decimal
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    "object_event": ("object_id", "event_id"),
    "character": ("name", "read", "born_place_id"),
    "character_place": ("character_id", "place_id"),
    "character_event": ("character_id", "event_id"),
    "term": ("name",),
}

# 指し先の対応は `reader.REFS` が持っている。ここで足すのは、
# 読み込みのときに構造から埋まる持ち主の欄だけ
OWNER_REFS = {
    "object_place": {"object_id": "object"},
    "object_event": {"object_id": "object"},
    "character_place": {"character_id": "character"},
    "character_event": {"character_id": "character"},
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
             "object_place", "object_event",
             "character_place", "character_event", "term"]
    with Session(engine) as session:
        for table in order:
            for rec in lib.of(table):
                session.add(rec.instance())
            session.flush()
        for rec in lib.documents:
            session.add(rec.instance())
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
    for table in owners:
        for deed in lib.of(f"{table}_event"):
            at = deed.values.get("start")
            target = event_by_id.get(deed.values.get("event_id"))
            if not at or at > when or (when.year - at.year) > reach:
                continue
            if target is None or target.values.get("place_id") not in scope:
                continue
            if visible(target) and kind_of(target) != "関係":
                deeds.append((table, deed, target))

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

    def label_of(table, rec):
        """個体は分類、人物は種族を添える。どちらか無ければ種別名で代える。"""
        if table == "character":
            return rec.values.get("race_id") or "人物"
        return rec.values.get("kind") or rec.values.get("kind_id") or "個体"

    section("4 その場にいる者", [
        f"- {o.values['name']}（{label_of(t, o)}）{_span(o)}{wide(s)}"
        for t, o, s in sorted(present, key=lambda p: str(p[1].values["name"]))])

    section("5 この射程での行動（何を失ったか）", [
        f"- {_year(d.values['start'])} "
        f"{by_id[d.values[f'{t}_id']][1].values['name']}: {e.values['name']}"
        for t, d, e in sorted(deeds, key=lambda p: p[1].values["start"])])

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

def template(table: str) -> str:
    fields = reader.FIELDS[table]
    head = ["---"] + [f"{k}:" for k in fields] + ["---", "",
                      f"# （{reader.LABEL[table]}の名）", "",
                      "（上段の下は人間が読む文章。",
                      "  上段に書いたことを繰り返さない）"]
    where = {
        "place": "novels/worlds/<世界線>/**/<場所>/<場所>.md",
        "event": "novels/worlds/<世界線>/**/<場所>/events/{時刻}_{名}.md",
        "kind": "novels/objects/<世界線>/<種別>.md",
        "object": "novels/objects/<世界線>/**/<個体>/<個体>.md",
        "object_place": "novels/objects/<世界線>/**/<個体>/places/{時刻}_{場所}.md",
        "object_event": "novels/objects/<世界線>/**/<個体>/actions/{時刻}_{名}.md",
        "character": "novels/characters/<出身地>/**/<人名>/<人名>.md",
        "character_place":
            "novels/characters/<出身地>/**/<人名>/places/{時刻}_{場所}.md",
        "character_event":
            "novels/characters/<出身地>/**/<人名>/actions/{時刻}_{名}.md",
        "term": "novels/terms/**/<語>/<語>.md",
    }[table]
    return f"<!-- 置き場所: {where} -->\n" + "\n".join(head) + "\n"


# ---------------------------------------------------------------- 書き出す

# サブレコード種別 → (持ち主の列, サブディレクトリ, ルート)
OWNER_DIR = {
    "event": ("place_id", "events", "worlds"),
    "object_place": ("object_id", "places", "objects"),
    "object_event": ("object_id", "actions", "objects"),
    "character_place": ("character_id", "places", "characters"),
    "character_event": ("character_id", "actions", "characters"),
}

ROOT_DIR = {"place": "worlds", "kind": "objects", "object": "objects",
            "character": "characters", "term": "terms"}


def _record_path(table: str, rec_id: str, owner_id: str | None) -> str:
    """id から置き場所を逆に組む。**id がそのまま置き場所を持っている。**"""
    if table in ROOT_DIR:
        root = ROOT_DIR[table]
        if table == "kind":
            return os.path.join(NOVELS, root, f"{rec_id}.md")
        base = rec_id.rsplit("/", 1)[-1]
        return os.path.join(NOVELS, root, rec_id, f"{base}.md")
    _, subdir, root = OWNER_DIR[table]
    stem = rec_id[len(owner_id) + 1:]
    return os.path.join(NOVELS, root, owner_id, subdir, f"{stem}.md")


def dump(engine, lib: reader.Library) -> list[str]:
    """DB の行をマークダウンへ書き戻す。**書き出したパスを返す。**

    上段の欄は `reader.FIELDS` を逆に辿って作る。他を指す欄は、
    **指し先の実際の `name`** に戻す（id の末尾ではない。出来事などは
    id の末尾が時刻つきのファイル名なので、id の末尾＝名前ではない）。
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
        # 参照先テーブルごとの id → 名前。出来事は id の末尾が時刻つきの
        # ファイル名なので、名前は別に持っている `name` 列から引く
        name_of: dict[str, dict[str, str]] = {}
        for table, model in reader.MODELS.items():
            if hasattr(model, "name"):
                name_of[table] = {
                    row.id: row.name
                    for row in session.query(model.id, model.name)}

        written = []
        for table, model in reader.MODELS.items():
            owner_col = OWNER_DIR.get(table, (None,))[0]
            for row in session.query(model).order_by(model.id):
                head = {}
                for key, column in reader.FIELDS[table].items():
                    if key == "名":
                        continue
                    value = getattr(row, column, None)
                    if value in (None, ""):
                        continue
                    target = reader.REFS.get(table, {}).get(column)
                    if isinstance(value, stamp.Stamp):
                        value = str(value)
                    elif target:
                        value = name_of.get(target, {}).get(value, value)
                    elif isinstance(value, decimal.Decimal):
                        value = float(value)
                        if value == int(value):
                            value = int(value)
                    elif isinstance(value, float) and value == int(value):
                        value = int(value)
                    head[key] = value
                owner_id = getattr(row, owner_col) if owner_col else None
                path = existing_path.get((table, row.id)) \
                    or _record_path(table, row.id, owner_id)
                text_body = (row.text or "").strip()
                content = ("---\n"
                           + yaml.safe_dump(head, allow_unicode=True,
                                            sort_keys=False,
                                            default_flow_style=False)
                           + "---\n\n" + text_body + "\n")
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

def documents(engine) -> list:
    """db に入っている本文をぜんぶ返す（`schema.Document` の行）。"""
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        rows = session.query(schema.Document).order_by(
            schema.Document.story, schema.Document.kind,
            schema.Document.number, schema.Document.id).all()
        session.expunge_all()
        return rows


def read_document(engine, path: str) -> str:
    """本文を一件読む。**`path` は `novels/` からの相対パス。**

    `stories/<作品>/episodes/001.md` のほか、`<作品>/001` のような
    省いた書き方でも引ける。見つからなければ `LookupError`。
    """
    rows = documents(engine)
    by_id = {row.id: row for row in rows}
    if path in by_id:
        return by_id[path].text
    hits = [row for row in rows if row.id.endswith(f"/{path}")
            or row.id.endswith(f"/{path}.md")
            or f"{row.story}/{row.kind}" == path
            or (row.number is not None
                and f"{row.story}/{row.number:03d}" == path)]
    if len(hits) == 1:
        return hits[0].text
    if not hits:
        raise LookupError(f"「{path}」という本文は db に無い")
    raise LookupError("どれか一つに絞れない: "
                      + ", ".join(row.id for row in hits))


def write_document(engine, path: str, text: str) -> str:
    """本文を一件、db へ書き入れる（無ければ作る）。**戻り値は id。**

    マークダウンはここでは触らない。ファイルになるのは `save`（書き出し）。
    """
    from sqlalchemy.orm import Session

    rel = path.replace(os.sep, "/").lstrip("/")
    if not rel.startswith("stories/"):
        raise ValueError("本文は stories/ の下にだけ置ける")
    if not rel.endswith(".md"):
        raise ValueError("本文のパスは .md で終える")
    parts = rel.split("/")
    story = parts[1] if len(parts) > 2 else ""
    stem = os.path.splitext(parts[-1])[0]
    if len(parts) > 3 and parts[2] == "episodes":
        kind, number = "episode", int(stem) if stem.isdigit() else None
    elif stem in ("meta", "plot"):
        kind, number = stem, None
    else:
        kind, number = "other", None

    if not text.endswith("\n"):
        text += "\n"

    with Session(engine) as session:
        row = session.get(schema.Document, rel)
        if row is None:
            row = schema.Document(id=rel)
            session.add(row)
        row.story, row.kind, row.number, row.text = story, kind, number, text
        session.commit()
    return rel


def dump_documents(engine) -> list[str]:
    """db の本文をマークダウンへ書き戻す。**書き出したパスを返す。**

    中身が変わらないファイルは書き直さない。db から消した本文は
    こちらでは消さない（消すのは作者の手でやる）。
    """
    written = []
    for row in documents(engine):
        path = os.path.join(NOVELS, *row.id.split("/"))
        content = row.text or ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                if fh.read() == content:
                    continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(os.path.relpath(path, REPO))
    return written


# ---------------------------------------------------------------- 入口

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="不備を探す")
    sub.add_parser("load", help="**作業開始時。** マークダウンを db へ読み込む")
    sub.add_parser("build", help="load と同じ（旧い呼び名）")
    sub.add_parser("save", help="**作業終了時。** db をマークダウンへ書き出す")

    p = sub.add_parser("stories", help="本文の一覧を出す")
    p.add_argument("--work", help="作品名で絞る")

    p = sub.add_parser("read", help="本文を一件読む（db から）")
    p.add_argument("path", help="stories/<作品>/episodes/001.md など")

    p = sub.add_parser("write", help="本文を一件書く（db へ）")
    p.add_argument("path", help="stories/<作品>/episodes/003.md")
    p.add_argument("--file", required=True,
                   help="本文の入ったファイル。`-` で標準入力")

    p = sub.add_parser("brief", help="断面を出す")
    p.add_argument("--place", required=True)
    p.add_argument("--time", required=True)
    p.add_argument("--reach", type=int, default=60)
    p.add_argument("--full", action="store_true",
                   help="裏も出す。**本文を書くあいだは付けない**")

    p = sub.add_parser("list", help="一覧")
    p.add_argument("--kind", required=True, choices=sorted(KINDS))
    p.add_argument("--world")

    p = sub.add_parser("show", help="一件読む")
    p.add_argument("id")

    p = sub.add_parser("template", help="雛形を出す")
    p.add_argument("--kind", required=True, choices=sorted(KINDS))

    p = sub.add_parser("index", help="用語索引を書き出す")
    p.add_argument("--world", required=True)

    p = sub.add_parser("sql", help="組んだ db に直接問い合わせる")
    p.add_argument("query")

    sub.add_parser("dump", help="db の行をマークダウンへ書き戻す")

    args = ap.parse_args(argv)

    if args.command == "template":
        print(template(KINDS[args.kind]), end="")
        return 0

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
              f"（レコード {len(lib.records)} / 本文 {len(lib.documents)}）")
        return 0

    if args.command == "brief":
        print(brief(lib, args.place, reader.parse_time(args.time),
                    args.reach, args.full))
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
        for rec in lib.records:
            if args.id in (rec.id, rec.values.get("name")):
                print(f"# {reader.LABEL[rec.table]} / {rec.id}")
                print(f"# {os.path.relpath(rec.path, REPO)}\n")
                for key, column in reader.FIELDS[rec.table].items():
                    if rec.values.get(column) not in (None, ""):
                        print(f"{key}: {rec.values[column]}")
                print("\n" + rec.values.get("text", ""))
                return 0
        print(f"「{args.id}」が見つからない", file=sys.stderr)
        return 1

    if args.command == "index":
        out = os.path.join(NOVELS, "worlds", args.world, "glossary.md")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(index(lib, args.world) + "\n")
        print(f"{os.path.relpath(out, REPO)} を書き直した")
        return 0

    if args.command == "sql":
        if not os.path.exists(DB):
            build(lib)
        from sqlalchemy import text
        with schema.open_db(DB).connect() as conn:
            for row in conn.execute(text(args.query)):
                print("\t".join("" if v is None else str(v) for v in row))
        return 0

    if args.command in ("stories", "read", "write"):
        if not os.path.exists(DB):
            build(lib)
        engine = schema.open_db(DB)

        if args.command == "stories":
            for row in documents(engine):
                if args.work and args.work != row.story:
                    continue
                print(f"{row.id}\t{row.kind}\t{len(row.text)} 字")
            return 0

        if args.command == "read":
            try:
                print(read_document(engine, args.path), end="")
            except LookupError as err:
                print(err, file=sys.stderr)
                return 1
            return 0

        text = (sys.stdin.read() if args.file == "-"
                else open(args.file, encoding="utf-8").read())
        try:
            rel = write_document(engine, args.path, text)
        except ValueError as err:
            print(err, file=sys.stderr)
            return 1
        print(f"{rel} を db へ書いた（save で md に出る）")
        return 0

    if args.command == "save":
        if not os.path.exists(DB):
            print("先に load して db を組む", file=sys.stderr)
            return 1
        engine = schema.open_db(DB)
        written = dump(engine, lib) + dump_documents(engine)
        for path in written:
            print(f"更新: {path}")
        print(f"{len(written)} 件を書き出した" if written else "変更なし")
        return 0

    if args.command == "dump":
        if not os.path.exists(DB):
            print("先に build して db を組む", file=sys.stderr)
            return 1
        engine = schema.open_db(DB)
        written = dump(engine, lib) + dump_documents(engine)
        for path in written:
            print(f"更新: {path}")
        print(f"{len(written)} 件を書き直した" if written else "変更なし")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
