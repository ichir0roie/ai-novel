#!/usr/bin/env python3
"""新しい構造のマークダウンを読んで、`tools/schema.py` のレコードに起こす。

**置き場所がレコードの種類を決める。** 上段は中身だけを持つ。

```
novels/
  worlds/<世界>/<世界>.md                    Place（その世界の根）
  worlds/<世界線>/**/<場所>/<場所>.md          Place（ディレクトリ名と同じ名の md）
  worlds/<世界線>/**/<場所>/events/{時刻}_{名}.md   Event
  objects/<世界線>/<種別>.md                  Kind（種別）
  objects/<世界線>/**/<個体>/<個体>.md         Object（個体。群として振る舞うもの）
  objects/<世界線>/**/<個体>/places/{時刻}_{場所}.md  ObjectPlace（居場所の推移）
  objects/<世界線>/**/<個体>/actions/{時刻}_{名}.md   ObjectAction（行動）
  characters/<出身地>/**/<人名>/<人名>.md      Character（人物。一人ひとり）
  characters/<出身地>/**/<人名>/places/{時刻}_{場所}.md  CharacterPlace（居場所の推移）
  characters/<出身地>/**/<人名>/actions/{時刻}_{名}.md   CharacterAction（行動）
  terms/**/<語>/<語>.md                      Term（入れ子。親は上のディレクトリ）
  stories/<作品>/…                           本文。台帳には入らない
```

`{時刻}` は `{年}_{mm}_{dd}`、時刻まで要るなら `{年}_{mm}_{dd}_{hhmmss}`
（`4340_01_01_耐用年数の満了.md` / `4340_01_01_093000_耐用年数の満了.md`）。
上段の中は `y/mm/dd hh:mm:ss` で書く（`tools/stamp.py`）。

**ディレクトリ名と同じ名前の md だけが場所のレコード。** それ以外の md は
自由文書として読み飛ばされるので、`解釈表.md` のような読み物を隣に置いてよい。

**id は資料に書かない。** 読むときに、上位のレコードの id と自分の名から
ここで採番する（`入植星/森`、`森/43400101000000_耐用年数の満了`）。
他のレコードを指す欄（`親` `場所` `出来事` `分類` `種族` `所属`）には
**名前を書く。** 名前から id へは読み込みのときに寄せ直す。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import yaml

import schema
import stamp

# ---------------------------------------------------------------- 上段

_FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)


def split_front_matter(src: str) -> tuple[dict, str]:
    """`---` で挟んだ YAML と、その下の本文に割る。

    上段が無ければ `({}, 全文)` を返す。
    """
    m = _FM.match(src.lstrip("﻿"))
    if not m:
        return {}, src.strip()
    head = yaml.safe_load(m.group(1)) or {}
    if not isinstance(head, dict):
        raise ReadError("上段が辞書になっていない")
    # 空欄（`没:`）は None で来る。空文字と同じ扱いにしておく
    return {k: v for k, v in head.items()}, m.group(2).strip()


class ReadError(Exception):
    """一つの md を読むあいだに起きた不備。ファイル名を添えて報告する。"""


# ---------------------------------------------------------------- 時刻

def parse_time(value) -> stamp.Stamp | None:
    """`43600712` も `4360-07-12` も `4360` も受け取って `Stamp` にする。

    **`datetime` は使わない。** 作中の年は 9999 を越えるので持てない
    （`tools/stamp.py`）。
    """
    try:
        return stamp.Stamp.parse(value)
    except stamp.StampError as err:
        raise ReadError(str(err)) from None


def format_time(when: stamp.Stamp | None) -> str:
    """ファイル名の頭へ戻す。"""
    return "" if when is None else when.stem()


# `4340_1_1_名` と `4340_1_1_093000_名`
_STAMPED = re.compile(r"\A(\d+_\d{1,2}_\d{1,2}(?:_\d{6})?)_(.+)\Z")


def split_stamped_name(stem: str) -> tuple[stamp.Stamp, str]:
    """`4340_01_01_耐用年数の満了` を時刻と名に割る。"""
    m = _STAMPED.match(stem)
    when = stamp.Stamp.from_stem(m.group(1)) if m else None
    if when is None:
        raise ReadError(
            "ファイル名が {年}_{mm}_{dd}_{名}.md "
            "（時刻まで入れるなら {年}_{mm}_{dd}_{hhmmss}_{名}.md）になっていない")
    return when, m.group(2)


# ---------------------------------------------------------------- 欄の対応表

FIELDS: dict[str, dict[str, str]] = {
    "place": {
        "名": "name", "種別": "kind", "親": "parent_id",
        "世界番号": "location_world", "惑星番号": "location_planet",
        "経度": "location_longitude", "緯度": "location_latitude",
        "高度": "location_altitude",
        "X": "location_x", "Y": "location_y", "Z": "location_z",
        "始": "start", "終": "end",
    },
    "event": {
        "名": "name", "種別": "kind", "時": "time",
        "親": "parent_event_id", "場所": "place_id",
        "始": "start", "終": "end",
    },
    "kind": {
        "名": "name", "読み": "read", "種別": "kind",
        "世界": "root_place_id", "始": "start", "終": "end",
    },
    "object": {
        "名": "name", "読み": "read", "種別": "kind",
        "分類": "kind_id", "世界": "root_place_name",
        "世界影響力": "world_influence",
        "始": "start", "終": "end",
    },
    "object_place": {
        "場所": "place_id", "始": "start", "終": "end",
    },
    "object_event": {
        "出来事": "event_id", "始": "start", "終": "end",
    },
    "character": {
        "名": "name", "読み": "read",
        "出身": "born_place_id", "種族": "race_id", "所属": "belong_id",
        "性別": "sex", "背丈": "height", "体格": "build", "見た目": "looks",
        "一人称": "first_person", "二人称": "second_person",
        "三人称": "third_person", "口調": "tone",
        "性格": "personality", "感情": "emotion", "思想": "thought",
        "欲": "desire", "嘘": "lie", "必要": "need", "恐れ": "fear",
        "能力": "ability", "代償": "cost",
        "世界影響力": "world_influence",
        "生": "start", "没": "end",
    },
    "character_place": {
        "場所": "place_id", "始": "start", "終": "end",
    },
    "character_event": {
        "出来事": "event_id", "始": "start", "終": "end",
    },
    "term": {
        "名": "name", "種別": "kind",
        "世界": "restrict_world_id", "星": "restrict_planet_id",
        "場所": "restrict_place_id",
    },
}

MODELS = {
    "place": schema.Place,
    "event": schema.Event,
    "kind": schema.Kind,
    "object": schema.Object,
    "object_place": schema.ObjectPlace,
    "object_event": schema.ObjectAction,
    "character": schema.Character,
    "character_place": schema.CharacterPlace,
    "character_event": schema.CharacterAction,
    "term": schema.Term,
}

TIME_COLUMNS = {"time", "start", "end"}

# 他のレコードを指す欄。**名前で書いてあっても id へ寄せ直す。**
# 資料に id は書かないので、上段に入るのは常に名前のほう。
REFS: dict[str, dict[str, str]] = {
    "place": {"parent_id": "place"},
    "event": {"place_id": "place", "parent_event_id": "event"},
    "kind": {"root_place_id": "place"},
    "object": {"root_place_name": "place", "kind_id": "kind"},
    "object_place": {"place_id": "place"},
    "object_event": {"event_id": "event"},
    "character": {"born_place_id": "place", "race_id": "kind",
                  "belong_id": "object"},
    "character_place": {"place_id": "place"},
    "character_event": {"event_id": "event"},
    "term": {"parent_term_id": "term", "restrict_world_id": "place",
             "restrict_planet_id": "place", "restrict_place_id": "place"},
}

LABEL = {
    "place": "場所", "event": "出来事", "kind": "種別", "object": "個体",
    "object_place": "居場所", "object_event": "行動",
    "character": "人物", "character_place": "人物居場所",
    "character_event": "人物行動", "term": "語",
}

# 数で持つ欄。文字で書かれていても数へ寄せ直す
NUMBER_COLUMNS = {"height", "world_influence"}


# ---------------------------------------------------------------- 読んだ結果

@dataclass
class Record:
    table: str
    path: str
    values: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.values.get("id", "")

    def instance(self):
        return MODELS[self.table](**self.values)


@dataclass
class Library:
    """novels/ を一度歩いた結果。"""

    root: str
    records: list[Record] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    stories: list[str] = field(default_factory=list)

    def of(self, table: str) -> list[Record]:
        return [r for r in self.records if r.table == table]


# ---------------------------------------------------------------- 一件を読む

def read_record(path: str, table: str, defaults: dict) -> Record:
    with open(path, encoding="utf-8") as fh:
        head, body = split_front_matter(fh.read())

    fields = FIELDS[table]
    values = dict(defaults)
    for key, raw in head.items():
        column = fields.get(str(key))
        if column is None:
            raise ReadError(
                f"{LABEL[table]}に無い欄「{key}」。"
                f"欄を増やしたいなら tools/schema.py を直す"
            )
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        values[column] = parse_time(raw) if column in TIME_COLUMNS else raw

    for column in TIME_COLUMNS:
        if values.get(column) is not None and not isinstance(
                values[column], stamp.Stamp):
            values[column] = parse_time(values[column])

    for column in NUMBER_COLUMNS:
        if column in values and not isinstance(values[column], (int, float)):
            digits = re.sub(r"[^\d.]", "", str(values[column]))
            if not digits:
                raise ReadError(f"{column} を数として読めない: {values[column]!r}")
            values[column] = float(digits)

    values["text"] = body
    for column in ("name", "read", "kind"):
        if column in fields.values():
            values.setdefault(column, "")
    return Record(table, path, values)


# ---------------------------------------------------------------- 全体を歩く

def _place_dirs(world_dir: str):
    """`<場所>/<場所>.md` を持つディレクトリを、浅い順に返す。"""
    found = []
    for current, dirs, files in os.walk(world_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        name = os.path.basename(current)
        if f"{name}.md" in files:
            found.append(current)
    return found


def _read_owners(lib, fail, *, root, table, owner_column,
                 sub_tables, defaults):
    """`<入れ物>/**/<名>/<名>.md` と、その下の `places/` `actions/` を読む。

    個体（`objects/`）と人物（`characters/`）は、置き場所と欄が違うだけで
    形は同じ。**一か所で読む。** マーカーは `<場所>/<場所>.md` と同じく、
    ディレクトリ名と同じ名前の md。
    """
    place_table, event_table = sub_tables
    for top in sorted(_listdir(root)):
        top_dir = os.path.join(root, top)
        if not os.path.isdir(top_dir):
            continue
        for current, dirs, files in os.walk(top_dir):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            name = os.path.basename(current)
            marker = f"{name}.md"
            if marker not in files:
                continue
            path = os.path.join(current, marker)
            trail = os.path.relpath(current, root).replace(os.sep, "/")
            try:
                owner = read_record(path, table, defaults(top, name, trail))
            except (ReadError, yaml.YAMLError) as err:
                fail(path, err)
                continue
            lib.records.append(owner)

            for sub, sub_table, ref in (
                ("places", place_table, "place_id"),
                ("actions", event_table, "event_id"),
            ):
                for item in _stamped_files(os.path.join(current, sub)):
                    try:
                        when, label = split_stamped_name(_stem(item))
                        lib.records.append(read_record(item, sub_table, {
                            "id": f"{owner.id}/{_stem(item)}",
                            owner_column: owner.id, "start": when,
                            **({ref: label} if sub_table == place_table else {}),
                        }))
                    except (ReadError, yaml.YAMLError) as err:
                        fail(item, err)


def read_library(novels_dir: str) -> Library:
    """`novels/` を歩いて、全レコードと不備を集める。"""
    lib = Library(root=novels_dir)

    def fail(path: str, err: Exception):
        lib.problems.append(f"{os.path.relpath(path, novels_dir)}: {err}")

    # --- 場所と出来事 -----------------------------------------------------
    worlds_dir = os.path.join(novels_dir, "worlds")
    place_id_of_dir: dict[str, str] = {}

    for world in sorted(_listdir(worlds_dir)):
        world_dir = os.path.join(worlds_dir, world)
        if not os.path.isdir(world_dir):
            continue
        for place_dir in _place_dirs(world_dir):
            name = os.path.basename(place_dir)
            path = os.path.join(place_dir, f"{name}.md")
            parent = place_id_of_dir.get(os.path.dirname(place_dir))
            try:
                rec = read_record(path, "place", {
                    "id": f"{parent}/{name}" if parent else name,
                    "name": name,
                    **({"parent_id": parent} if parent else {}),
                })
            except (ReadError, yaml.YAMLError) as err:
                fail(path, err)
                continue
            place_id_of_dir[place_dir] = rec.id
            lib.records.append(rec)


    for place_dir, place_id in place_id_of_dir.items():
        for path in _stamped_files(os.path.join(place_dir, "events")):
            try:
                when, name = split_stamped_name(_stem(path))
                lib.records.append(read_record(path, "event", {
                    "id": f"{place_id}/{_stem(path)}", "name": name,
                    "time": when, "place_id": place_id,
                }))
            except (ReadError, yaml.YAMLError) as err:
                fail(path, err)

    # --- 種別 -------------------------------------------------------------
    for world, path in _world_files(os.path.join(novels_dir, "objects")):
        try:
            lib.records.append(read_record(path, "kind", {
                "id": f"{world}/{_stem(path)}", "name": _stem(path),
                "root_place_id": world,
            }))
        except (ReadError, yaml.YAMLError) as err:
            fail(path, err)

    # --- 個体と、その居場所・行動 -----------------------------------------
    _read_owners(
        lib, fail,
        root=os.path.join(novels_dir, "objects"),
        table="object", owner_column="object_id",
        sub_tables=("object_place", "object_event"),
        defaults=lambda world, name, trail: {
            "id": trail, "name": name, "root_place_name": world,
        },
    )

    # --- 人物と、その居場所・行動 -----------------------------------------
    _read_owners(
        lib, fail,
        root=os.path.join(novels_dir, "characters"),
        table="character", owner_column="character_id",
        sub_tables=("character_place", "character_event"),
        defaults=lambda born, name, trail: {
            "id": trail, "name": name, "born_place_id": born,
        },
    )

    # --- 語（入れ子）------------------------------------------------------
    _read_terms(lib, fail, os.path.join(novels_dir, "terms"))

    # --- 本文（読むだけ。台帳には入れない） -------------------------------
    stories_dir = os.path.join(novels_dir, "stories")
    for current, dirs, files in os.walk(stories_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        lib.stories += [os.path.join(current, f)
                        for f in sorted(files) if f.endswith(".md")]

    _resolve_refs(lib)
    return lib


def _read_terms(lib: Library, fail, terms_dir: str) -> None:
    """`terms/**/<語>.md`（子を持たない語）と `terms/**/<語>/<語>.md`
    （子を持つ語。下にぶら下がる語を置ける）を、浅いほうから読む。

    **入れ子が上下を表す。** `魔力/魔力切れ.md` と置けば、
    魔力切れは魔力にぶら下がる。子を持たない語に、空の入れ物ディレクトリは
    要らない。id は親の id と語の名から採番する。
    """
    parent_of_dir: dict[str, str] = {}
    for current, dirs, files in os.walk(terms_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        name = os.path.basename(current)
        own_marker = f"{name}.md"
        container_parent = parent_of_dir.get(os.path.dirname(current))

        own_id = None
        if own_marker in files:
            path = os.path.join(current, own_marker)
            try:
                rec = read_record(path, "term", {
                    "id": f"{container_parent}/{name}" if container_parent else name,
                    "name": name,
                    **({"parent_term_id": container_parent} if container_parent else {}),
                })
            except (ReadError, yaml.YAMLError) as err:
                fail(path, err)
            else:
                own_id = rec.id
                lib.records.append(rec)

        effective_parent = own_id or container_parent
        parent_of_dir[current] = effective_parent

        for leaf in sorted(files):
            if leaf == own_marker or not leaf.endswith(".md"):
                continue
            leaf_name = leaf[:-len(".md")]
            path = os.path.join(current, leaf)
            if not leaf_name:
                fail(path, ReadError("ファイル名が空。語の名を付ける"))
                continue
            try:
                rec = read_record(path, "term", {
                    "id": f"{effective_parent}/{leaf_name}"
                          if effective_parent else leaf_name,
                    "name": leaf_name,
                    **({"parent_term_id": effective_parent}
                       if effective_parent else {}),
                })
            except (ReadError, yaml.YAMLError) as err:
                fail(path, err)
                continue
            lib.records.append(rec)

    # 上の語で決めた縛りは、下の語も引き継ぐ
    by_id = {r.id: r for r in lib.of("term")}

    def _parent_of(rec_or_values) -> "Record | None":
        parent_id = rec_or_values.values.get("parent_term_id")
        return by_id.get(parent_id) if parent_id else None

    for rec in lib.of("term"):
        seen = {rec.id}
        parent = _parent_of(rec)
        while parent is not None:
            if parent.id in seen:
                fail(rec.path, ReadError(
                    f"語の親をたどると自分に戻ってくる（「{parent.id}」で循環）"))
                break
            seen.add(parent.id)
            for column in ("restrict_world_id", "restrict_planet_id",
                           "restrict_place_id"):
                if not rec.values.get(column) and parent.values.get(column):
                    rec.values[column] = parent.values[column]
            parent = _parent_of(parent)


def _resolve_refs(lib: Library) -> None:
    """他のレコードを名前で指している欄を、採番した id へ寄せ直す。

    同じ名が二つあって決められないときは、不備として上げる。
    **黙って片方を選ばない。**
    """
    known: dict[str, set[str]] = {}
    by_name: dict[str, dict[str, list[str]]] = {}
    for table in MODELS:
        known[table] = {r.id for r in lib.of(table)}
        names: dict[str, list[str]] = {}
        for rec in lib.of(table):
            names.setdefault(str(rec.values.get("name") or ""), []).append(rec.id)
        by_name[table] = names

    for rec in lib.records:
        for column, table in REFS.get(rec.table, {}).items():
            value = rec.values.get(column)
            if not value or value in known[table]:
                continue
            hits = by_name[table].get(str(value), [])
            if len(hits) == 1:
                rec.values[column] = hits[0]
            elif len(hits) > 1:
                lib.problems.append(
                    f"{os.path.relpath(rec.path, lib.root)}: "
                    f"{column} の「{value}」が{LABEL[table]}に {len(hits)} 件ある。"
                    f"名を分ける")


# ---------------------------------------------------------------- 小道具

def _listdir(path: str):
    return os.listdir(path) if os.path.isdir(path) else []


def _md_files(path: str):
    return [os.path.join(path, f) for f in sorted(_listdir(path))
            if f.endswith(".md") and not f.startswith("README")]


def _stamped_files(path: str):
    return [p for p in _md_files(path) if _STAMPED.match(_stem(p))]


def _world_files(path: str):
    for world in sorted(_listdir(path)):
        world_dir = os.path.join(path, world)
        if os.path.isdir(world_dir):
            for item in _md_files(world_dir):
                yield world, item


def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]
