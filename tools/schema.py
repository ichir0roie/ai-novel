#!/usr/bin/env python3
"""台帳の形。**DB の列と、マークダウンの構造を、ここ一か所で決めている。**

ここを直すと、DB の列・マークダウンの形・検査の内容が同時に変わる。

**入れ物は二種類ある。**

| | 何で書くか | 何を入れるか |
| --- | --- | --- |
| `TABLES` | `records/*.md` の**表**。一行 = 一レコード | 行が短くて数が多いもの。出来事・行動・数・関係・火種 |
| `ENTRIES` | **1 ファイル = 1 レコード。** front matter ＋ 本文 | 文章のつくもの。人物・物・用語・概念 |

ENTRIES では、front matter が**レコードとして管理する形**、本文が**文章として書く形**。
**同じファイルに併存させる**ことで、二重管理にならないようにしている。

    from schema import TABLES, ENTRIES, LEDGERS, create_db, headers

読み方と使いどころは core/chronicle.md。
"""
import os

from sqlalchemy import Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 列の種類
TEXT = "text"      # ただの文字列
STAMP = "stamp"    # 西暦。4360 / 4360-07 / 4360-07-12。並べ替え用に _k 列が対になる
NUM = "num"        # 数。文字が混ざっていても数だけ拾う


def md(header, kind=TEXT, req=False, ref=None):
    """マークダウン側の名前と、その約束ごと。

    header — 表なら**列見出し**、記事なら **front matter のキー**。これが機械の読む鍵
    req    — 空を許さない
    ref    — 他の台帳の id を指す（検査で使う）
    """
    return {"md": header, "kind": kind, "req": req, "ref": ref}


DERIVED = {"derived": True}   # マークダウンには書かない、組み上げのときに作る列


class Base(DeclarativeBase):
    """全台帳の親。"""


class Row:
    """どの台帳も持つもの。

    pk  — 内部の連番。マークダウンには出ない
    src — その行がどのファイルの何行目から来たか。**検査の出力で効く**
    """

    pk: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    src: Mapped[str] = mapped_column(String, default="", info=DERIVED)

    source = "table"    # "table"（records/*.md の表）か "entry"（1 ファイル 1 レコード）
    md_file = ""        # 表のときの台帳ファイル名
    entry_kind = ""     # 記事のときの front matter「記録」の値
    dir_hint = ""       # 記事を置く目安の場所（人間の整理用。強制しない）
    ja = ""             # 日本語の呼び名
    about = ""          # 何を貯めるか
    key_col = None      # 一意な id の列名（あれば）
    uniq = ()           # 重複を禁じる列の組
    inherit = ()        # 同じ id の初出から引き継ぐ列
    id_prefix = ""      # id を自動で振るときの接頭辞


class EntryCols:
    """1 ファイル 1 レコードの記事だけが持つ列。

    path — リポジトリからの相対パス。**断面からこれを辿って本文を読む**
    body — front matter の下の文章。まるごと入れてあるので `sql` で本文も探せる
    """

    source = "entry"
    path: Mapped[str] = mapped_column(String, default="", info=DERIVED)
    body: Mapped[str] = mapped_column(String, default="", info=DERIVED)


# ===================================================== 表（records/*.md）

class Place(Row, Base):
    __tablename__ = "place"
    md_file, ja = "場所.md", "場所"
    about = "地理。親をたどって内側・外側を決める"
    key_col, id_prefix = "id", "pl"

    id: Mapped[str] = mapped_column(String, info=md("id", req=True))
    name: Mapped[str] = mapped_column(String, info=md("名", req=True))
    star: Mapped[str] = mapped_column(String, default="", info=md("星"))
    kind: Mapped[str] = mapped_column(String, default="", info=md("種別"))
    parent: Mapped[str] = mapped_column(
        String, default="", info=md("親", ref="place"))
    note: Mapped[str] = mapped_column(String, default="", info=md("備考"))

    x: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=md("X座標", NUM))
    y: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=md("Y座標", NUM))
    z: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=md("Z座標", NUM))
    p: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=md("惑星座標", NUM))
    w: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=md("世界座標", NUM))


class Event(Row, Base):
    __tablename__ = "event"
    md_file, ja = "出来事.md", "出来事"
    about = "起きたこと"
    key_col, id_prefix = "id", "ev"

    id: Mapped[str] = mapped_column(String, info=md("id", req=True))
    t0: Mapped[str] = mapped_column(String, info=md("年", STAMP, req=True))
    t0_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    t1: Mapped[str] = mapped_column(String, default="", info=md("終年", STAMP))
    t1_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    star: Mapped[str] = mapped_column(String, default="", info=md("星"))
    place: Mapped[str] = mapped_column(
        String, default="", info=md("場所", ref="place"))
    kind: Mapped[str] = mapped_column(String, default="", info=md("種別"))
    scale: Mapped[float | None] = mapped_column(
        Float, nullable=True, info=md("規模", NUM))
    visibility: Mapped[str] = mapped_column(String, default="", info=md("公開"))
    summary: Mapped[str] = mapped_column(String, info=md("出来事", req=True))
    actors: Mapped[str] = mapped_column(
        String, default="", info=md("関与", ref="actor"))
    ref: Mapped[str] = mapped_column(String, default="", info=md("出典"))


class Act(Row, Base):
    __tablename__ = "act"
    md_file, ja = "行動.md", "行動"
    about = "主語のある出来事。動機・代償・結果つき"
    key_col, id_prefix = "id", "dd"

    id: Mapped[str] = mapped_column(String, info=md("id", req=True))
    t0: Mapped[str] = mapped_column(String, info=md("年", STAMP, req=True))
    t0_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    actor: Mapped[str] = mapped_column(
        String, info=md("人物", req=True, ref="actor"))
    place: Mapped[str] = mapped_column(
        String, default="", info=md("場所", ref="place"))
    deed: Mapped[str] = mapped_column(String, info=md("行動", req=True))
    motive: Mapped[str] = mapped_column(String, default="", info=md("動機"))
    cost: Mapped[str] = mapped_column(String, default="", info=md("代償"))
    result: Mapped[str] = mapped_column(String, default="", info=md("結果"))
    visibility: Mapped[str] = mapped_column(String, default="", info=md("公開"))
    ref: Mapped[str] = mapped_column(String, default="", info=md("出典"))


class Metric(Row, Base):
    __tablename__ = "metric"
    md_file, ja = "指標.md", "指標"
    about = "数で追えるもの。人口・資源・値段"
    uniq = ("t0", "star", "place", "name")

    t0: Mapped[str] = mapped_column(String, info=md("年", STAMP, req=True))
    t0_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    star: Mapped[str] = mapped_column(String, default="", info=md("星"))
    place: Mapped[str] = mapped_column(
        String, default="", info=md("場所", ref="place"))
    name: Mapped[str] = mapped_column(String, info=md("指標", req=True))
    value: Mapped[float | None] = mapped_column(
        Float, nullable=True, info=md("値", NUM, req=True))
    unit: Mapped[str] = mapped_column(String, default="", info=md("単位"))
    ref: Mapped[str] = mapped_column(String, default="", info=md("出典"))


class Bond(Row, Base):
    __tablename__ = "bond"
    md_file, ja = "関係.md", "関係"
    about = "誰と誰が、どういう間柄か。強度 -3〜3"
    uniq = ("t0", "a", "b", "kind")

    t0: Mapped[str] = mapped_column(String, info=md("年", STAMP, req=True))
    t0_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    t1: Mapped[str] = mapped_column(String, default="", info=md("終年", STAMP))
    t1_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    a: Mapped[str] = mapped_column(
        String, info=md("人物A", req=True, ref="actor"))
    b: Mapped[str] = mapped_column(
        String, info=md("人物B", req=True, ref="actor"))
    kind: Mapped[str] = mapped_column(String, info=md("関係", req=True))
    level: Mapped[float | None] = mapped_column(
        Float, nullable=True, info=md("強度", NUM))
    ref: Mapped[str] = mapped_column(String, default="", info=md("出典"))


class Tension(Row, Base):
    __tablename__ = "tension"
    md_file, ja = "火種.md", "火種"
    about = "張っているもの。値 0〜5 と、限界で起きること"
    key_col, id_prefix = "id", "ts"
    uniq = ("id", "t0")
    inherit = ("name", "axis", "edge", "star", "place")

    id: Mapped[str] = mapped_column(String, info=md("id", req=True))
    t0: Mapped[str] = mapped_column(String, info=md("年", STAMP, req=True))
    t0_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    star: Mapped[str] = mapped_column(String, default="", info=md("星"))
    place: Mapped[str] = mapped_column(
        String, default="", info=md("場所", ref="place"))
    name: Mapped[str] = mapped_column(String, default="", info=md("名"))
    axis: Mapped[str] = mapped_column(String, default="", info=md("対立軸"))
    level: Mapped[float | None] = mapped_column(
        Float, nullable=True, info=md("値", NUM, req=True))
    edge: Mapped[str] = mapped_column(String, default="", info=md("限界で起きること"))
    ref: Mapped[str] = mapped_column(String, default="", info=md("出典"))


# ============================================ 記事（1 ファイル 1 レコード）

class Actor(EntryCols, Row, Base):
    __tablename__ = "actor"
    entry_kind, ja = "人物", "人物"
    dir_hint = "<星>/characters/"
    about = "行動の主語になれるもの。個人・組織・国・集団・仕組み"
    key_col, id_prefix = "id", "ac"

    id: Mapped[str] = mapped_column(String, info=md("id", req=True))
    name: Mapped[str] = mapped_column(String, info=md("名", req=True))
    read: Mapped[str] = mapped_column(String, default="", info=md("読み"))
    kind: Mapped[str] = mapped_column(String, default="", info=md("種別"))
    star: Mapped[str] = mapped_column(String, default="", info=md("星"))
    line: Mapped[str] = mapped_column(String, default="", info=md("系統"))
    born: Mapped[str] = mapped_column(String, default="", info=md("生", STAMP))
    born_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    died: Mapped[str] = mapped_column(String, default="", info=md("没", STAMP))
    died_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    org: Mapped[str] = mapped_column(
        String, default="", info=md("所属", ref="actor"))
    place: Mapped[str] = mapped_column(
        String, default="", info=md("居所", ref="place"))
    note: Mapped[str] = mapped_column(String, default="", info=md("一言"))
    ref: Mapped[str] = mapped_column(String, default="", info=md("出典"))


class Thing(EntryCols, Row, Base):
    __tablename__ = "thing"
    entry_kind, ja = "物", "物"
    dir_hint = "<星>/objects/"
    about = "主語にならないもの。道具・資源・現象・施設"
    key_col, id_prefix = "id", "th"

    id: Mapped[str] = mapped_column(String, info=md("id", req=True))
    name: Mapped[str] = mapped_column(String, info=md("名", req=True))
    read: Mapped[str] = mapped_column(String, default="", info=md("読み"))
    kind: Mapped[str] = mapped_column(String, default="", info=md("種別"))
    star: Mapped[str] = mapped_column(String, default="", info=md("星"))
    place: Mapped[str] = mapped_column(
        String, default="", info=md("場所", ref="place"))
    born: Mapped[str] = mapped_column(String, default="", info=md("生", STAMP))
    born_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    died: Mapped[str] = mapped_column(String, default="", info=md("没", STAMP))
    died_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    note: Mapped[str] = mapped_column(String, default="", info=md("一言"))
    ref: Mapped[str] = mapped_column(String, default="", info=md("出典"))


class Term(EntryCols, Row, Base):
    __tablename__ = "term"
    entry_kind, ja = "用語", "用語"
    dir_hint = "terms/"
    about = ("作中に出る語。正式名称と通称、表と裏、いつ使われたか。"
             "**語の側の記録。** 実体（人物・物）が別にあるなら「実体」で指す")
    key_col, id_prefix = "id", "tm"

    id: Mapped[str] = mapped_column(String, info=md("id", req=True))
    name: Mapped[str] = mapped_column(String, info=md("名", req=True))
    read: Mapped[str] = mapped_column(String, default="", info=md("読み"))
    kind: Mapped[str] = mapped_column(String, default="", info=md("種別"))
    star: Mapped[str] = mapped_column(String, default="", info=md("星"))
    born: Mapped[str] = mapped_column(String, default="", info=md("生", STAMP))
    born_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    died: Mapped[str] = mapped_column(String, default="", info=md("没", STAMP))
    died_k: Mapped[int | None] = mapped_column(
        Integer, nullable=True, info=DERIVED)
    formal: Mapped[str] = mapped_column(String, default="", info=md("正式名称"))
    common: Mapped[str] = mapped_column(String, default="", info=md("通称"))
    face: Mapped[str] = mapped_column(String, default="", info=md("表"))
    back: Mapped[str] = mapped_column(String, default="", info=md("裏"))
    entity: Mapped[str] = mapped_column(String, default="", info=md("実体"))
    state: Mapped[str] = mapped_column(String, default="", info=md("状態"))
    ref: Mapped[str] = mapped_column(String, default="", info=md("出典"))


TABLES = (Place, Event, Act, Metric, Bond, Tension)
ENTRIES = (Actor, Thing, Term)
# 組み上げる順。場所と人物が先（他がここの id を指すため）
LEDGERS = (Place, Actor, Thing, Term,
           Event, Act, Metric, Bond, Tension)

ENTRY_KEY = "記録"     # front matter のこのキーで、どの記事かを決める


def md_cols(model):
    """マークダウンに書く列を、定義順で返す。"""
    return [c for c in model.__table__.columns if c.info.get("md")]


def headers(model):
    """表なら列見出し、記事なら front matter のキー。**これが形そのもの**。"""
    return [c.info["md"] for c in md_cols(model)]


def by_header(model):
    return {c.info["md"]: c for c in md_cols(model)}


def find(name):
    """テーブル名・ファイル名・日本語名のどれでも引けるようにする。"""
    for model in LEDGERS:
        names = {model.__tablename__, model.ja, model.entry_kind}
        if model.md_file:
            names |= {model.md_file, model.md_file.removesuffix(".md")}
        if name in names - {""}:
            return model
    raise KeyError(name)


def entry_model(kind):
    """front matter の「記録」の値から記事の型を引く。"""
    for model in ENTRIES:
        if model.entry_kind == kind:
            return model
    raise KeyError(kind)


def create_db(path):
    """**db ファイルを作り直して、空のテーブルを張る。**

    台帳から何度でも組み直せるので、既にあれば消して作り直す。
    """
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    return engine


def open_db(path):
    """既にある db を開く。"""
    return create_engine(f"sqlite:///{os.path.abspath(path)}", future=True)


if __name__ == "__main__":
    for group, title in ((TABLES, "表（records/*.md）"), (ENTRIES, "記事（1 ファイル 1 レコード）")):
        print(f"== {title}")
        for m in group:
            where = f"records/{m.md_file}" if m.md_file else f"{ENTRY_KEY}: {m.entry_kind}"
            print(f"{m.ja}（{m.__tablename__} / {where}）— {m.about}")
            print("  " + " | ".join(headers(m)))
