#!/usr/bin/env python3
"""台帳の形。**DB の列と、マークダウンの列見出しを、ここ一か所で決めている。**

ここを直すと、DB の列・マークダウンの表の形・検査の内容が同時に変わる。
台帳を増やしたいときは、このファイルにクラスを足して `LEDGERS` に並べる。

    from schema import LEDGERS, create_db, headers

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
    """マークダウン側の列見出しと、その約束ごと。

    header — 表の見出し。**これが機械の読む鍵になる**
    req    — 空を許さない
    ref    — 他の台帳の id を指す列（検査で使う）
    """
    return {"md": header, "kind": kind, "req": req, "ref": ref}


DERIVED = {"derived": True}   # マークダウンには出ない、組み上げのときに作る列


class Base(DeclarativeBase):
    """全台帳の親。"""


class Row:
    """どの台帳も持つもの。

    pk  — 内部の連番。マークダウンには出ない
    src — その行がどのファイルの何行目から来たか。**検査の出力で効く**
    """

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    src: Mapped[str] = mapped_column(String, default="", info=DERIVED)

    md_file = ""        # 台帳のファイル名
    ja = ""             # 日本語の呼び名
    about = ""          # 何を貯めるか
    key_col = None      # 一意な id の列名（あれば）
    uniq = ()           # 重複を禁じる列の組
    inherit = ()        # 同じ id の初出から引き継ぐ列
    id_prefix = ""      # id を自動で振るときの接頭辞


class Place(Row, Base):
    __tablename__ = "place"
    md_file, ja = "場所.md", "場所"
    about = "地理。親をたどって内側・外側を決める"
    key_col, id_prefix = "id", "pl"

    id: Mapped[str] = mapped_column(String, info=md("id", req=True))
    name: Mapped[str] = mapped_column(String, info=md("名", req=True))
    star: Mapped[str] = mapped_column(String, default="", info=md("星"))
    kind: Mapped[str] = mapped_column(String, default="", info=md("種別"))
    parent: Mapped[str] = mapped_column(String, default="", info=md("親", ref="place"))
    note: Mapped[str] = mapped_column(String, default="", info=md("備考"))


class Actor(Row, Base):
    __tablename__ = "actor"
    md_file, ja = "人物.md", "人物"
    about = "行動の主語になれるもの。個人・組織・国・集団・仕組み"
    key_col, id_prefix = "id", "ac"

    id: Mapped[str] = mapped_column(String, info=md("id", req=True))
    name: Mapped[str] = mapped_column(String, info=md("名", req=True))
    kind: Mapped[str] = mapped_column(String, default="", info=md("種別"))
    star: Mapped[str] = mapped_column(String, default="", info=md("星"))
    line: Mapped[str] = mapped_column(String, default="", info=md("系統"))
    born: Mapped[str] = mapped_column(String, default="", info=md("生", STAMP))
    born_k: Mapped[int | None] = mapped_column(Integer, nullable=True, info=DERIVED)
    died: Mapped[str] = mapped_column(String, default="", info=md("没", STAMP))
    died_k: Mapped[int | None] = mapped_column(Integer, nullable=True, info=DERIVED)
    org: Mapped[str] = mapped_column(String, default="", info=md("所属", ref="actor"))
    place: Mapped[str] = mapped_column(String, default="", info=md("居所", ref="place"))
    note: Mapped[str] = mapped_column(String, default="", info=md("備考"))


class Event(Row, Base):
    __tablename__ = "event"
    md_file, ja = "出来事.md", "出来事"
    about = "起きたこと"
    key_col, id_prefix = "id", "ev"

    id: Mapped[str] = mapped_column(String, info=md("id", req=True))
    t0: Mapped[str] = mapped_column(String, info=md("年", STAMP, req=True))
    t0_k: Mapped[int | None] = mapped_column(Integer, nullable=True, info=DERIVED)
    t1: Mapped[str] = mapped_column(String, default="", info=md("終年", STAMP))
    t1_k: Mapped[int | None] = mapped_column(Integer, nullable=True, info=DERIVED)
    star: Mapped[str] = mapped_column(String, default="", info=md("星"))
    place: Mapped[str] = mapped_column(String, default="", info=md("場所", ref="place"))
    kind: Mapped[str] = mapped_column(String, default="", info=md("種別"))
    scale: Mapped[float | None] = mapped_column(Float, nullable=True, info=md("規模", NUM))
    visibility: Mapped[str] = mapped_column(String, default="", info=md("公開"))
    summary: Mapped[str] = mapped_column(String, info=md("出来事", req=True))
    actors: Mapped[str] = mapped_column(String, default="", info=md("関与", ref="actor"))
    ref: Mapped[str] = mapped_column(String, default="", info=md("出典"))


class Act(Row, Base):
    __tablename__ = "act"
    md_file, ja = "行動.md", "行動"
    about = "主語のある出来事。動機・代償・結果つき"
    key_col, id_prefix = "id", "dd"

    id: Mapped[str] = mapped_column(String, info=md("id", req=True))
    t0: Mapped[str] = mapped_column(String, info=md("年", STAMP, req=True))
    t0_k: Mapped[int | None] = mapped_column(Integer, nullable=True, info=DERIVED)
    actor: Mapped[str] = mapped_column(String, info=md("人物", req=True, ref="actor"))
    place: Mapped[str] = mapped_column(String, default="", info=md("場所", ref="place"))
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
    t0_k: Mapped[int | None] = mapped_column(Integer, nullable=True, info=DERIVED)
    star: Mapped[str] = mapped_column(String, default="", info=md("星"))
    place: Mapped[str] = mapped_column(String, default="", info=md("場所", ref="place"))
    name: Mapped[str] = mapped_column(String, info=md("指標", req=True))
    value: Mapped[float | None] = mapped_column(Float, nullable=True, info=md("値", NUM, req=True))
    unit: Mapped[str] = mapped_column(String, default="", info=md("単位"))
    ref: Mapped[str] = mapped_column(String, default="", info=md("出典"))


class Bond(Row, Base):
    __tablename__ = "bond"
    md_file, ja = "関係.md", "関係"
    about = "誰と誰が、どういう間柄か。強度 -3〜3"
    uniq = ("t0", "a", "b", "kind")

    t0: Mapped[str] = mapped_column(String, info=md("年", STAMP, req=True))
    t0_k: Mapped[int | None] = mapped_column(Integer, nullable=True, info=DERIVED)
    t1: Mapped[str] = mapped_column(String, default="", info=md("終年", STAMP))
    t1_k: Mapped[int | None] = mapped_column(Integer, nullable=True, info=DERIVED)
    a: Mapped[str] = mapped_column(String, info=md("人物A", req=True, ref="actor"))
    b: Mapped[str] = mapped_column(String, info=md("人物B", req=True, ref="actor"))
    kind: Mapped[str] = mapped_column(String, info=md("関係", req=True))
    level: Mapped[float | None] = mapped_column(Float, nullable=True, info=md("強度", NUM))
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
    t0_k: Mapped[int | None] = mapped_column(Integer, nullable=True, info=DERIVED)
    star: Mapped[str] = mapped_column(String, default="", info=md("星"))
    place: Mapped[str] = mapped_column(String, default="", info=md("場所", ref="place"))
    name: Mapped[str] = mapped_column(String, default="", info=md("名"))
    axis: Mapped[str] = mapped_column(String, default="", info=md("対立軸"))
    level: Mapped[float | None] = mapped_column(Float, nullable=True, info=md("値", NUM, req=True))
    edge: Mapped[str] = mapped_column(String, default="", info=md("限界で起きること"))
    ref: Mapped[str] = mapped_column(String, default="", info=md("出典"))


# 組み上げる順。場所と人物が先（他がここの id を指すため）
LEDGERS = (Place, Actor, Event, Act, Metric, Bond, Tension)


def md_cols(model):
    """マークダウンに出る列を、表の並び順で返す。"""
    return [c for c in model.__table__.columns if c.info.get("md")]


def headers(model):
    """マークダウンの表の見出し。**これが表の形そのもの**。"""
    return [c.info["md"] for c in md_cols(model)]


def by_header(model):
    return {c.info["md"]: c for c in md_cols(model)}


def stamp_of(model, col):
    """STAMP 列に対になる並べ替え用の列名。"""
    return f"{col.name}_k" if col.info.get("kind") == STAMP else None


def find(name):
    """テーブル名・ファイル名・日本語名のどれでも引けるようにする。"""
    for model in LEDGERS:
        if name in (model.__tablename__, model.md_file, model.ja, model.md_file.removesuffix(".md")):
            return model
    raise KeyError(name)


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
    for m in LEDGERS:
        print(f"{m.ja}（{m.__tablename__} / {m.md_file}）— {m.about}")
        print("  | " + " | ".join(headers(m)) + " |")
