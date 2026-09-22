#!/usr/bin/env python3
"""novel.test.db の全テーブルにモックデータを流し込む。

使い方:
    python -m DEM.tool.test.seed_mock_db                       各テーブル 100 件
    python -m DEM.tool.test.seed_mock_db --n 300               件数を変える
    python -m DEM.tool.test.seed_mock_db --seed 12345          シードを指定して再現
    python -m DEM.tool.test.seed_mock_db --recreate            ファイルを消して作り直してから入れる
"""
from DEM.tool.test import TEST_DB_PATH  # noqa: F401  db を novel.test.db に固定する(schema より先に読む)

import argparse
import os
import random

from factory.random import reseed_random
from sqlalchemy import create_engine, func, select

from DEM.db.schema import Base, create_db
from DEM.randomizer import mock_factories


def seed_mock_db(n=100, seed=None, recreate=False) -> dict[str, int]:
    """`novel.test.db` に、各テーブル `n` 件ずつ足す。戻り値はテーブルごとの総件数。"""
    path = os.path.abspath(TEST_DB_PATH)
    if recreate:
        engine = create_db(path)
    else:
        engine = create_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine)

    seed = seed if seed is not None else random.randrange(10**9)
    reseed_random(seed)

    mock_factories.bind(engine)
    try:
        for factory_class in mock_factories.ALL_FACTORIES:
            factory_class.create_batch(n)
        mock_factories.commit()
    finally:
        mock_factories._session.remove()

    with engine.connect() as conn:
        counts = {
            table.name: conn.execute(select(func.count()).select_from(table)).scalar_one()
            for table in Base.metadata.sorted_tables
        }
    engine.dispose()
    return counts


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=100, help="各テーブルに足す件数")
    p.add_argument("--seed", type=int, help="乱数シード(省略時は自動生成して表示)")
    p.add_argument("--recreate", action="store_true", help="db ファイルを消して空から作り直す")
    args = p.parse_args()

    seed = args.seed if args.seed is not None else random.randrange(10**9)
    print(f"seed = {seed}")
    counts = seed_mock_db(n=args.n, seed=seed, recreate=args.recreate)
    for name, count in counts.items():
        print(f"{name}\t{count}")


if __name__ == "__main__":
    main()
