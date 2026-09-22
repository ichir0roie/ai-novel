#!/usr/bin/env python3
"""schema.py の ORM モデルから、SQLAlchemy のマッパー情報を読んで pydantic モデルを自動で組む。

使い方:
    from schema_pydantic import to_model
    row = session.get(schema.Character, some_id)
    model = to_model(row)            # pydantic インスタンス
    model.model_dump_json()          # JSON 文字列
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, create_model
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase

import DEM.db.schema as schema
from DEM.db.stamp import Stamp

# 列の型 → pydantic (python) の型
_TYPE_MAP = {
    Decimal: float,
}


def _python_type(column_type) -> type:
    py_type = column_type.python_type
    return _TYPE_MAP.get(py_type, py_type)


def _field_type(column) -> type:
    if isinstance(column.type, schema.StampType):
        py_type = Stamp
    elif isinstance(column.type, schema.PolygonType):
        py_type = dict
    else:
        py_type = _python_type(column.type)
    return py_type | None if column.nullable else py_type


_MODELS: dict[type, type[BaseModel]] = {}


def _build_model(orm_cls: type[DeclarativeBase]) -> type[BaseModel]:
    """一つの ORM クラスから、対応する pydantic モデルを組む。"""
    mapper = sa_inspect(orm_cls)
    fields: dict[str, Any] = {}
    for column in mapper.columns:
        default = None if column.nullable or column.primary_key else ...
        fields[column.key] = (_field_type(column), default)

    model = create_model(
        orm_cls.__name__,
        __config__=ConfigDict(from_attributes=True, arbitrary_types_allowed=True),
        **fields,
    )
    return model


def _model_for(orm_cls: type[DeclarativeBase]) -> type[BaseModel]:
    model = _MODELS.get(orm_cls)
    if model is None:
        model = _build_model(orm_cls)
        _MODELS[orm_cls] = model
    return model


def to_model(row) -> BaseModel:
    """ORM インスタンス一件を、対応する pydantic モデルへ変換する。

    relationship でぶら下がる先(`Event.place` など)は含まない。
    列だけを持つ、素の一件分のデータになる。
    """
    return _model_for(type(row)).model_validate(row)


def to_dict(row) -> dict:
    """`to_model` の JSON 化しやすい dict 版(Stamp は文字列にする)。"""
    return _to_jsonable(to_model(row).model_dump())


def _to_jsonable(value):
    if isinstance(value, Stamp):
        return str(value)
    if isinstance(value, dict):
        return {key: _to_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(val) for val in value]
    return value


def to_json(row) -> str:
    """ORM インスタンス一件を JSON 文字列にする。"""
    import json
    return json.dumps(to_dict(row), ensure_ascii=False)


def relation_names(row, relations) -> dict:
    """**ロード済みの relationship から、関連レコードの名前だけを引く。**

    追加クエリ(旧 `query._name()`)を打たず、`selectinload` 等で
    あらかじめ読み込んである関連オブジェクトの `.name` を読むだけにする。
    未ロードの relationship(`lazy="noload"`)を渡すと素の SQLAlchemy が
    例外を投げるので、呼ぶ側は select 文に `options(selectinload(...))` を
    付けておく。

    `relations` はリレーション名のリスト(`["kind", "belong"]`。出力の
    キーは `"kind_name"` のように `_name` を足したもの)か、出力キーを
    変えたいときの `{"kind": "kind_name"}` のような辞書。値は関連レコードが
    無ければ `None`。
    """
    if isinstance(relations, dict):
        pairs = relations.items()
    else:
        pairs = [(name, f"{name}_name") for name in relations]
    result = {}
    for attribute, key in pairs:
        related = getattr(row, attribute, None)
        result[key] = None if related is None else getattr(related, "name", None)
    return result


def to_dict_with(row, *, relations=(), text: bool = True) -> dict:
    """`to_dict` に、ロード済み relationship の名前解決を重ねる。

    `text=False` なら `text` 欄を落とす(一覧を見るときなど、本文までは
    要らない場合に使う)。
    """
    data = to_dict(row)
    if not text:
        data.pop("text", None)
    data.update(relation_names(row, relations))
    return data


def models_for_all_tables() -> dict[str, type[BaseModel]]:
    """`schema.py` の全テーブルぶんの pydantic モデルを、テーブル名をキーに返す。"""
    result = {}
    for mapper in schema.Base.registry.mappers:
        orm_cls = mapper.class_
        result[orm_cls.__tablename__] = _model_for(orm_cls)
    return result
