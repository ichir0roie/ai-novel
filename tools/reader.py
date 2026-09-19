#!/usr/bin/env python3
"""新しい構造のマークダウンを読んで、`tools/schema.py` のレコードに起こす。

**置き場所がレコードの種類を決める。** データは中身だけを持つ。

```
novels/
  worlds/<世界>/<世界>.md                    Place（その世界の根）
  worlds/<世界線>/**/<場所>/<場所>.md          Place（ディレクトリ名と同じ名の md）
  worlds/<世界線>/**/<場所>/events/{時刻}_{名}.md   Event
  objects/<世界線>/<種別>.md                  Kind（種別）
  objects/<世界線>/**/<個体>/<個体>.md         Object（個体。群として振る舞うもの）
  objects/<世界線>/**/<個体>/places/{時刻}_{場所}.md  ObjectPlace（居場所の推移）
  objects/<世界線>/**/<個体>/events/{時刻}_{名}.md   Event（行動。個体つきの出来事）
  characters/<出身地>/**/<人名>/<人名>.md      Character（人物。一人ひとり）
  characters/<出身地>/**/<人名>/places/{時刻}_{場所}.md  CharacterPlace（居場所の推移）
  characters/<出身地>/**/<人名>/events/{時刻}_{名}.md   Event（行動。人物つきの出来事）
  terms/**/<語>/<語>.md                      Term（入れ子。親は上のディレクトリ）
  stories/<作品名>/meta.md                    Story（作品。企画。データを持つ）
  stories/<作品名>/episodes/{話数}.md          Episode（一話。**原稿そのもの**）
```

`{時刻}` は `{年}_{mm}_{dd}`、時刻まで要るなら `{年}_{mm}_{dd}_{hhmmss}`
（`4340_01_01_耐用年数の満了.md` / `4340_01_01_093000_耐用年数の満了.md`）。
データの中は `y/mm/dd hh:mm:ss` で書く（`tools/stamp.py`）。

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

import schema
import stamp

# ---------------------------------------------------------------- データ

_FM = re.compile(r"\A# data\s*\n(.*?)\n?# text\s*\n?(.*)\Z", re.S)


def split_front_matter(src: str) -> tuple[dict, str]:
    """`# data` と `# text` で分けた欄と、その下の本文に割る。

    データが無ければ `({}, 全文)` を返す。
    """
    m = _FM.match(src.lstrip("﻿"))
    if not m:
        return {}, src.strip()
    head: dict = {}
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ReadError(f"データの行が「欄:値」になっていない: {line!r}")
        # 空欄（`没:`）は空文字。無かったことにしておく
        head[key.strip()] = value.strip()
    return head, m.group(2).strip()


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
        "始": "start", "終": "end",
    },
    # 行動もここ。`人物` `個体` が誰の行動かを持ち、`親` が掛かり先の出来事
    "event": {
        "名": "name", "種別": "kind", "時": "time",
        "親": "parent_event_id", "場所": "place_id",
        "人物": "character_id", "個体": "object_id",
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
    "term": {
        "名": "name", "種別": "kind",
        "世界": "restrict_world_id", "星": "restrict_planet_id",
        "場所": "restrict_place_id",
    },
    "story": {
        "名": "name", "世界": "world_id", "場所": "place_id",
        "語り": "narration", "状態": "state", "始": "start", "終": "end",
    },
    # 本文のデータは `同期` だけ。話数はファイル名、題と字数は原稿から読む
    "episode": {"話数": "number", "題": "title", "字数": "letters",
                "同期": "synced"},
}

# 昔の欄名。読むときだけ受ける（書き出しは FIELDS のほうの名で揃える）。
# 行動は出来事へ統合したので、`出来事` は掛かり先の親を指す
ALIASES: dict[str, dict[str, str]] = {
    "event": {"出来事": "parent_event_id"},
}

MODELS = {
    "place": schema.Place,
    "event": schema.Event,
    "kind": schema.Kind,
    "object": schema.Object,
    "object_place": schema.ObjectPlace,
    "character": schema.Character,
    "character_place": schema.CharacterPlace,
    "term": schema.Term,
    "story": schema.Story,
    "episode": schema.Episode,
}

TIME_COLUMNS = {"time", "start", "end"}

# 他のレコードを指す欄。**名前で書いてあっても id へ寄せ直す。**
# 資料に id は書かないので、データに入るのは常に名前のほう。
REFS: dict[str, dict[str, str]] = {
    "place": {"parent_id": "place"},
    "event": {"place_id": "place", "parent_event_id": "event",
              "character_id": "character", "object_id": "object"},
    "kind": {"root_place_id": "place"},
    "object": {"root_place_name": "place", "kind_id": "kind"},
    "object_place": {"place_id": "place"},
    "character": {"born_place_id": "place", "race_id": "kind",
                  "belong_id": "object"},
    "character_place": {"place_id": "place"},
    "term": {"parent_term_id": "term", "restrict_world_id": "place",
             "restrict_planet_id": "place", "restrict_place_id": "place"},
    "story": {"world_id": "place", "place_id": "place"},
    "episode": {"story_id": "story"},
}

LABEL = {
    "place": "場所", "event": "出来事", "kind": "種別", "object": "個体",
    "object_place": "居場所",
    "character": "人物", "character_place": "人物居場所", "term": "語",
    "story": "作品", "episode": "話",
}

# 数で持つ欄。文字で書かれていても数へ寄せ直す
NUMBER_COLUMNS = {"height", "world_influence", "number", "letters"}

# 真偽で持つ欄。`オン` `済` `yes` のような書き方も受ける
BOOL_COLUMNS = {"synced"}
TRUE_WORDS = {"true", "yes", "on", "1", "オン", "済", "はい", "有"}


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
        column = fields.get(str(key)) or ALIASES.get(table, {}).get(str(key))
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

    for column in BOOL_COLUMNS:
        if column in values and not isinstance(values[column], bool):
            values[column] = str(values[column]).strip().lower() in TRUE_WORDS

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
    """`<入れ物>/**/<名>/<名>.md` と、その下の `places/` `events/` を読む。

    個体（`objects/`）と人物（`characters/`）は、置き場所と欄が違うだけで
    形は同じ。**一か所で読む。** マーカーは `<場所>/<場所>.md` と同じく、
    ディレクトリ名と同じ名前の md。

    **`events/` は出来事（`event`）になる。** 行動の別表は持たない。
    誰の行動かは `character_id` / `object_id`、掛かり先は `親`（`出来事`）。
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
            except ReadError as err:
                fail(path, err)
                continue
            lib.records.append(owner)

            for sub, sub_table, ref in (
                ("places", place_table, "place_id"),
                ("events", event_table, "parent_event_id"),
            ):
                for item in _stamped_files(os.path.join(current, sub)):
                    try:
                        when, label = split_stamped_name(_stem(item))
                        base = {"id": f"{owner.id}/{_stem(item)}",
                                owner_column: owner.id, "start": when}
                        if sub_table == place_table:
                            base[ref] = label
                        else:
                            # 行動＝出来事。名と時はファイル名から採る。
                            # 場所は掛かり先の出来事から継ぐ（_inherit_places）
                            base.update(name=label, time=when)
                        lib.records.append(read_record(item, sub_table, base))
                    except ReadError as err:
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
            except ReadError as err:
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
            except ReadError as err:
                fail(path, err)

    # --- 種別 -------------------------------------------------------------
    for world, path in _world_files(os.path.join(novels_dir, "objects")):
        try:
            lib.records.append(read_record(path, "kind", {
                "id": f"{world}/{_stem(path)}", "name": _stem(path),
                "root_place_id": world,
            }))
        except ReadError as err:
            fail(path, err)

    # --- 個体と、その居場所・行動 -----------------------------------------
    _read_owners(
        lib, fail,
        root=os.path.join(novels_dir, "objects"),
        table="object", owner_column="object_id",
        sub_tables=("object_place", "event"),
        defaults=lambda world, name, trail: {
            "id": trail, "name": name, "root_place_name": world,
        },
    )

    # --- 人物と、その居場所・行動 -----------------------------------------
    _read_owners(
        lib, fail,
        root=os.path.join(novels_dir, "characters"),
        table="character", owner_column="character_id",
        sub_tables=("character_place", "event"),
        defaults=lambda born, name, trail: {
            "id": trail, "name": name, "born_place_id": born,
        },
    )

    # --- 語（入れ子）------------------------------------------------------
    _read_terms(lib, fail, os.path.join(novels_dir, "terms"))

    # --- 作品と、その話 ---------------------------------------------------
    _read_stories(lib, fail, os.path.join(novels_dir, "stories"))

    _resolve_refs(lib)
    _fill_locations(lib)
    _inherit_places(lib)
    return lib


def _fill_locations(lib: Library) -> None:
    """場所の一意テキスト（`location_key`）を組む。

    **桁は上の場所から継ぐ。** 世界線・惑星番号を根に書けば、その配下の
    場所は自分の座標だけ書けばよい。

    鍵が付くのは、**自分で座標をひとつでも書いた場所だけ。** 何も書いて
    いない場所に上の桁だけを継がせると、隣の場所と同じ鍵になってしまう。
    同じ鍵が二つできたら不備として上げる（**一意でないと結べない**）。
    """
    places = {r.id: r for r in lib.of("place")}

    def inherited(rec: Record) -> dict:
        chain, seen = [], set()
        while rec is not None and rec.id not in seen:
            seen.add(rec.id)
            chain.append(rec)
            parent = rec.values.get("parent_id")
            rec = places.get(parent) if parent else None
        merged = {}
        for node in reversed(chain):          # 根から順に上書きしていく
            for column in schema.LOCATION_COLUMNS:
                if node.values.get(column) not in (None, ""):
                    merged[column] = node.values[column]
        return merged

    taken: dict[str, Record] = {}
    for rec in lib.of("place"):
        own = [rec.values.get(column) for column in schema.LOCATION_COLUMNS]
        if all(part in (None, "") for part in own):
            continue
        key = schema.location_text(inherited(rec))
        if key is None:
            continue
        if key in taken:
            lib.problems.append(
                f"{os.path.relpath(rec.path, lib.root)}: 場所の一意テキスト"
                f"「{key}」が {os.path.relpath(taken[key].path, lib.root)} "
                f"と重なっている。座標を分ける")
            continue
        taken[key] = rec
        rec.values["location_key"] = key


def _inherit_places(lib: Library) -> None:
    """行動の場所を、掛かり先の出来事から継ぐ。

    行動の md に `場所` を書いてあればそれを使う。書いていなければ、
    親の出来事をたどって最初に見つかった場所を入れる。
    **これで、場所と時刻だけで行動まで引ける。**
    """
    events = {r.id: r for r in lib.of("event")}
    for rec in lib.of("event"):
        if rec.values.get("place_id"):
            continue
        seen = {rec.id}
        parent = events.get(rec.values.get("parent_event_id"))
        while parent is not None and parent.id not in seen:
            seen.add(parent.id)
            if parent.values.get("place_id"):
                rec.values["place_id"] = parent.values["place_id"]
                break
            parent = events.get(parent.values.get("parent_event_id"))


def _read_terms(lib: Library, fail, terms_dir: str) -> None:
    """`terms/**/<語>.md`（子を持たない語）と `terms/**/<語>/<語>.md`
    （子を持つ語。下にぶら下がる語を置ける）を、浅いほうから読む。
    ディレクトリ自身の記事は `<語>.md` のほか、名を省いた `.md` でもよい。

    **入れ子が上下を表す。** `魔力/魔力切れ.md` と置けば、
    魔力切れは魔力にぶら下がる。子を持たない語に、空の入れ物ディレクトリは
    要らない。id は親の id と語の名から採番する。
    """
    parent_of_dir: dict[str, str] = {}
    for current, dirs, files in os.walk(terms_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        name = os.path.basename(current)
        # ディレクトリ自身の記事。名を省いた `.md` も同じ扱いにする
        own_marker = f"{name}.md" if f"{name}.md" in files else ".md"
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
            except ReadError as err:
                fail(path, err)
            else:
                own_id = rec.id
                lib.records.append(rec)

        effective_parent = own_id or container_parent
        parent_of_dir[current] = effective_parent

        for leaf in sorted(files):
            if leaf == own_marker or leaf == ".md" or not leaf.endswith(".md"):
                continue
            leaf_name = leaf[:-len(".md")]
            path = os.path.join(current, leaf)
            try:
                rec = read_record(path, "term", {
                    "id": f"{effective_parent}/{leaf_name}"
                          if effective_parent else leaf_name,
                    "name": leaf_name,
                    **({"parent_term_id": effective_parent}
                       if effective_parent else {}),
                })
            except ReadError as err:
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


# `3.md` のような、話数だけのファイル名。**ゼロ埋めしない**
# （`003.md` と書かれていても数として同じに読む）
_NUMBERED = re.compile(r"\A(\d+)\Z")


def _read_stories(lib: Library, fail, stories_dir: str) -> None:
    """`stories/<作品名>/meta.md` と `stories/<作品名>/episodes/{話数}.md` を読む。

    **作品の id は作品名、話の id は `<作品名>/<話数>`。** 話数はファイル名の
    数がそのまま入る（`3.md` なら 3）。**ゼロ埋めしない。** 話の `text` は
    原稿そのもので、データは持たない（本文のファイルにデータを足さない）。
    題は本文の先頭の見出し（`# 第 3 話　…`）から読む。

    `meta.md` の無いディレクトリは作品として採らない。企画を書く前の
    置き場や、`plot.md` だけの下書きを不備にしないため。
    """
    for name in sorted(_listdir(stories_dir)):
        story_dir = os.path.join(stories_dir, name)
        meta = os.path.join(story_dir, "meta.md")
        if not os.path.isdir(story_dir) or not os.path.exists(meta):
            continue
        try:
            story = read_record(meta, "story", {"id": name, "name": name})
        except ReadError as err:
            fail(meta, err)
            continue
        lib.records.append(story)
        lib.stories.append(meta)

        for path in _md_files(os.path.join(story_dir, "episodes")):
            found = _NUMBERED.match(_stem(path))
            if not found:
                fail(path, ReadError(
                    "本文のファイル名が話数（`3.md`）になっていない"))
                continue
            number = int(found.group(1))
            try:
                rec = read_record(path, "episode", {
                    "id": f"{story.id}/{number}", "story_id": story.id,
                    "number": number, "synced": False,
                })
            except ReadError as err:
                fail(path, err)
                continue
            body = rec.values.get("text", "")
            rec.values.setdefault("title", _episode_title(body))
            rec.values.setdefault("letters", len(body))
            lib.records.append(rec)
            lib.stories.append(path)


def _episode_title(body: str) -> str:
    """本文の先頭の見出しから、サブタイトルだけを取る。

    `# 第 3 話　外の土地の話` → `外の土地の話`。見出しが無ければ空。
    """
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("#"):
            continue
        head = line.lstrip("#").strip()
        m = re.match(r"\A第\s*\d+\s*話[　\s]*(.*)\Z", head)
        return (m.group(1) if m else head).strip()
    return ""


def _resolve_refs(lib: Library) -> None:
    """他のレコードを名前で指している欄を、採番した id へ寄せ直す。

    同じ名が二つあって決められないときは、不備として上げる。
    **黙って片方を選ばない。**
    """
    def is_action(table: str, rec_id: str) -> bool:
        """その出来事が、誰かの行動かどうか。"""
        rec = index.get((table, rec_id))
        return rec is not None and bool(
            rec.values.get("character_id") or rec.values.get("object_id"))

    index = {(r.table, r.id): r for r in lib.records}
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
            hits = [hit for hit in by_name[table].get(str(value), [])
                    if hit != rec.id]
            if len(hits) > 1 and table == "event":
                # 行動は出来事と同じ名を持つ（掛かり先と同じ名で置く）。
                # **指し先は、行動でないほうを採る。**
                plain = [hit for hit in hits if not is_action(table, hit)]
                if plain:
                    hits = plain
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
