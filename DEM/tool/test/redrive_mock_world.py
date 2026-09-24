#!/usr/bin/env python3
"""`redrive_world` を、AI の代わりに `MockAIClient` で `novel.test.db` に対して回す。

使い方:
    python -m DEM.tool.test.redrive_mock_world                     novel.test.db(無ければ novel.db を写して作る)を 2025 年から 120 回ぶん
    python -m DEM.tool.test.redrive_mock_world --max-days 30 --seed 1
    python -m DEM.tool.test.redrive_mock_world --copy-from world/novel.db  いまの novel.db を写し直してから回す
"""
from DEM.tool.test import TEST_DB_PATH  # noqa: F401  db を novel.test.db に固定する(schema より先に読む)

import argparse
import os
import shutil

from DEM.ai.time_keeper.main import loop_time
from DEM.db.schema import Stamp
from DEM.tool.danger import reset_world
from DEM.tool.test.mock_ai_client import MockAIClient

DEFAULT_SOURCE_DB = "world/novel.db"


def prepare_test_db(copy_from: str | None = None) -> None:
    """`copy_from` を渡せば必ず写し直す。渡さなければ、test db が無いときだけ `novel.db` から写す。"""
    if copy_from is None:
        if os.path.exists(TEST_DB_PATH):
            return
        copy_from = DEFAULT_SOURCE_DB
    if not os.path.exists(copy_from):
        raise FileNotFoundError(f"写し元の db が無い: {copy_from}")
    shutil.copy2(copy_from, TEST_DB_PATH)
    print(f"[redrive_mock] {copy_from} → {TEST_DB_PATH}")


def redrive_mock_world(
    year: int = 2025, max_days: int | None = 120, seed: int | None = None,
    copy_from: str | None = None,
) -> MockAIClient:
    prepare_test_db(copy_from)
    reset_world.reset_world()
    ai = MockAIClient(seed)
    last = loop_time(ai, Stamp(year), max_days)
    print(f"[redrive_mock] {TEST_DB_PATH}: {last} まで / {ai.usage_summary()}")
    return ai


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, default=2025, help="始める年")
    p.add_argument("--max-days", type=int, default=120,
                   help="ループを回す回数(0 ならプロットが尽きるまで)")
    p.add_argument("--seed", type=int, help="モック AI の乱数シード")
    p.add_argument("--copy-from", help="回す前にこの db を novel.test.db へ写す")
    args = p.parse_args()
    redrive_mock_world(
        year=args.year, max_days=args.max_days or None, seed=args.seed,
        copy_from=args.copy_from)


if __name__ == "__main__":
    main()
