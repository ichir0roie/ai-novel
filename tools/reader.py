#!/usr/bin/env python3
"""新しい構造のマークダウンを読んで、`tools/schema.py` のレコードに起こす。

**置き場所がレコードの種類を決める。** front matter は中身だけを持つ。

```
novels/
  worlds/<世界>/<世界>.md                    Place（その世界の根）
  worlds/<世界線>/**/<場所>/<場所>.md          Place（ディレクトリ名と同じ名の md）
  worlds/<世界線>/**/<場所>/events/{時刻}_{名}.md   Event
  objects/<世界線>/<種別>.md                  Kind（種別）
  objects/<世界線>/**/<個体>/object.md         Object（個体。群として振る舞うもの）
  objects/<世界線>/**/<個体>/places/{時刻}_{場所}.md  ObjectPlace（居場所の推移）
  objects/<世界線>/**/<個体>/actions/{時刻}_{名}.md   ObjectAction（行動）
  characters/<出身地>/**/<人名>/character.md   Character（人物。一人ひとり）
  characters/<出身地>/**/<人名>/places/{時刻}_{場所}.md  CharacterPlace（居場所の推移）
  characters/<出身地>/**/<人名>/actions/{時刻}_{名}.md   CharacterAction（行動）
  terms/<語>.md                              Term
  stories/<作品>/…                           本文。台帳には入らない
```

`{時刻}` は `yyyymmddhhmmss`。頭から欠けた分は書かなくてよい（`4360` /
`436007` / `43600712` も受け取り、足りない桁は 1 月 1 日 0 時で埋める）。

**ディレクトリ名と同じ名前の md だけが場所のレコード。** それ以外の md は
自由文書として読み飛ばされるので、`解釈表.md` のような読み物を隣に置いてよい。
"""
from __future__ import annotations

import datetime
import os
import re
from dataclasses import dataclass, field

import yaml

import schema

# ---------------------------------------------------------------- front matter

_FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)


def split_front_matter(src: str) -> tuple[dict, str]:
    """`---` で挟んだ YAML と、その下の本文に割る。

    front matter が無ければ `({}, 全文)` を返す。
    """
    m = _FM.match(src.lstrip("﻿"))
    if not m:
        return {}, src.strip()
    head = yaml.safe_load(m.group(1)) or {}
    if not isinstance(head, dict):
        raise ReadError("front matter が辞書になっていない")
    # 空欄（`没:`）は None で来る。空文字と同じ扱いにしておく
    return {k: v for k, v in head.items()}, m.group(2).strip()


class ReadError(Exception):
    """一つの md を読むあいだに起きた不備。ファイル名を添えて報告する。"""


# ---------------------------------------------------------------- 時刻

_STAMP = re.compile(r"\A(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?\Z")


def parse_time(value) -> datetime.datetime | None:
    """`43600712` も `4360-07-12` も `4360` も受け取って datetime にする。

    **年は西暦。** 粒度は混ぜてよい。書かれなかった桁は頭の値で埋める。
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    text = str(value).strip()
    if not text:
        return None

    m = _STAMP.match(text)
    if m:
        y, mo, d, h, mi, s = (int(g) if g else None for g in m.groups())
        return datetime.datetime(y, mo or 1, d or 1, h or 0, mi or 0, s or 0)

    parts = [p for p in re.split(r"[-/ :T]", text) if p != ""]
    if not parts or not all(p.isdigit() for p in parts):
        raise ReadError(f"時刻として読めない: {value!r}")
    nums = [int(p) for p in parts][:6]
    nums += [1, 1][len(nums) - 1:3] if len(nums) < 3 else []
    nums += [0] * (6 - len(nums))
    return datetime.datetime(*nums)


def format_time(when: datetime.datetime | None) -> str:
    """ファイル名に使う 14 桁へ戻す。"""
    return "" if when is None else when.strftime("%Y%m%d%H%M%S")


_STAMPED = re.compile(r"\A(\d{4,14})_(.+)\Z")


def split_stamped_name(stem: str) -> tuple[datetime.datetime, str]:
    """`43400101000000_耐用年数の満了` を時刻と名に割る。"""
    m = _STAMPED.match(stem)
    if not m:
        raise ReadError("ファイル名が {時刻}_{名}.md になっていない")
    return parse_time(m.group(1)), m.group(2)


# ---------------------------------------------------------------- 欄の対応表

COMMON = {"id": "id", "出典": "src"}

FIELDS: dict[str, dict[str, str]] = {
    "place": {
        **COMMON,
        "名": "name", "種別": "kind", "親": "parent_id",
        "世界番号": "location_world", "惑星番号": "location_planet",
        "経度": "location_longitude", "緯度": "location_latitude",
        "高度": "location_altitude",
        "X": "location_x", "Y": "location_y", "Z": "location_z",
        "始": "start", "終": "end",
    },
    "event": {
        **COMMON,
        "名": "name", "種別": "kind", "時": "time",
        "親": "parent_event_id", "場所": "place_id",
        "始": "start", "終": "end",
    },
    "kind": {
        **COMMON,
        "名": "name", "読み": "read", "種別": "kind",
        "世界": "root_place_id", "始": "start", "終": "end",
    },
    "object": {
        **COMMON,
        "名": "name", "読み": "read", "種別": "kind",
        "分類": "kind_id", "世界": "root_place_name",
        "始": "start", "終": "end",
    },
    "object_place": {
        **COMMON,
        "場所": "place_id", "始": "start", "終": "end",
    },
    "object_event": {
        **COMMON,
        "出来事": "event_id", "始": "start", "終": "end",
    },
    "character": {
        **COMMON,
        "名": "name", "読み": "read",
        "出身": "born_place_id", "種族": "race_id", "所属": "belong_id",
        "性別": "sex", "背丈": "height", "体格": "build", "見た目": "looks",
        "一人称": "first_person", "二人称": "second_person",
        "三人称": "third_person", "口調": "tone",
        "性格": "personality", "感情": "emotion", "思想": "thought",
        "欲": "desire", "嘘": "lie", "必要": "need", "恐れ": "fear",
        "能力": "ability", "代償": "cost",
        "生": "start", "没": "end",
    },
    "character_place": {
        **COMMON,
        "場所": "place_id", "始": "start", "終": "end",
    },
    "character_event": {
        **COMMON,
        "出来事": "event_id", "始": "start", "終": "end",
    },
    "term": {
        **COMMON,
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

# 場所を指す欄。名前で書いてあっても id へ寄せ直す
PLACE_REFS = {
    "place": {"parent_id"},
    "event": {"place_id"},
    "kind": {"root_place_id"},
    "object": {"root_place_name"},
    "object_place": {"place_id"},
    "character": {"born_place_id"},
    "character_place": {"place_id"},
    "term": {"restrict_world_id", "restrict_planet_id", "restrict_place_id"},
}

LABEL = {
    "place": "場所", "event": "出来事", "kind": "種別", "object": "個体",
    "object_place": "居場所", "object_event": "行動",
    "character": "人物", "character_place": "人物居場所",
    "character_event": "人物行動", "term": "語",
}

# 数で持つ欄。文字で書かれていても数へ寄せ直す
NUMBER_COLUMNS = {"height"}


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
        if isinstance(values.get(column), (str, int)):
            values[column] = parse_time(values[column])

    for column in NUMBER_COLUMNS:
        if column in values and not isinstance(values[column], (int, float)):
            digits = re.sub(r"[^\d.]", "", str(values[column]))
            if not digits:
                raise ReadError(f"{column} を数として読めない: {values[column]!r}")
            values[column] = float(digits)

    values["text"] = body
    values.setdefault("src", "")
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


def _read_owners(lib, fail, *, root, marker, table, owner_column,
                 sub_tables, defaults):
    """`<入れ物>/**/<名>/{marker}` と、その下の `places/` `actions/` を読む。

    個体（`objects/`）と人物（`characters/`）は、置き場所と欄が違うだけで
    形は同じ。**一か所で読む。**
    """
    place_table, event_table = sub_tables
    for top in sorted(_listdir(root)):
        top_dir = os.path.join(root, top)
        if not os.path.isdir(top_dir):
            continue
        for current, dirs, files in os.walk(top_dir):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            if marker not in files:
                continue
            name = os.path.basename(current)
            path = os.path.join(current, marker)
            try:
                owner = read_record(path, table, defaults(top, name))
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
                    "id": name, "name": name,
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
                    "id": _stem(path), "name": name,
                    "time": when, "place_id": place_id,
                }))
            except (ReadError, yaml.YAMLError) as err:
                fail(path, err)

    # --- 種別 -------------------------------------------------------------
    for world, path in _world_files(os.path.join(novels_dir, "objects")):
        try:
            lib.records.append(read_record(path, "kind", {
                "id": _stem(path), "name": _stem(path), "root_place_id": world,
            }))
        except (ReadError, yaml.YAMLError) as err:
            fail(path, err)

    # --- 個体と、その居場所・行動 -----------------------------------------
    _read_owners(
        lib, fail,
        root=os.path.join(novels_dir, "objects"),
        marker="object.md", table="object", owner_column="object_id",
        sub_tables=("object_place", "object_event"),
        defaults=lambda world, name: {
            "id": name, "name": name, "root_place_name": world,
        },
    )

    # --- 人物と、その居場所・行動 -----------------------------------------
    _read_owners(
        lib, fail,
        root=os.path.join(novels_dir, "characters"),
        marker="character.md", table="character", owner_column="character_id",
        sub_tables=("character_place", "character_event"),
        defaults=lambda born, name: {
            "id": name, "name": name, "born_place_id": born,
        },
    )

    # --- 語 ---------------------------------------------------------------
    for path in _md_files(os.path.join(novels_dir, "terms")):
        try:
            lib.records.append(read_record(path, "term", {
                "id": _stem(path), "name": _stem(path),
            }))
        except (ReadError, yaml.YAMLError) as err:
            fail(path, err)

    # --- 本文（読むだけ。台帳には入れない） -------------------------------
    stories_dir = os.path.join(novels_dir, "stories")
    for current, dirs, files in os.walk(stories_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        lib.stories += [os.path.join(current, f)
                        for f in sorted(files) if f.endswith(".md")]

    _resolve_place_refs(lib)
    return lib


def _resolve_place_refs(lib: Library) -> None:
    """場所を名前で書いてある欄を、id へ寄せ直す。"""
    by_name: dict[str, list[str]] = {}
    known = set()
    for rec in lib.of("place"):
        known.add(rec.id)
        by_name.setdefault(str(rec.values.get("name") or ""), []).append(rec.id)

    for rec in lib.records:
        for column in PLACE_REFS.get(rec.table, ()):
            value = rec.values.get(column)
            if not value or value in known:
                continue
            hits = by_name.get(str(value), [])
            if len(hits) == 1:
                rec.values[column] = hits[0]


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
