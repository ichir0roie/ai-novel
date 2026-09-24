#!/usr/bin/env python3
from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import CompoundSelect, Select

from db.schema import engine

DUMP_DIR = os.path.join("tmp", "sql", "dump")

__all__ = ["DUMP_DIR", "compile_select", "dump_select"]


def compile_select(stmt: Select | CompoundSelect) -> str:
    # literal_binds で `Stamp` などの値も `StampType.process_bind_param` を通って整数で埋まる
    compiled = stmt.compile(dialect=engine.dialect,
                            compile_kwargs={"literal_binds": True})
    return str(compiled)


def dump_select(stmt: Select | CompoundSelect, dump_dir: str = DUMP_DIR) -> str:
    sql = compile_select(stmt)
    os.makedirs(dump_dir, exist_ok=True)
    path = os.path.join(dump_dir, datetime.now().strftime("%Y%m%d%H%M%S") + ".sql")
    with open(path, "w", encoding="utf-8") as f:
        f.write(sql + ";\n")
    return path
