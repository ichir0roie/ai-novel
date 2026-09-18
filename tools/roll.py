#!/usr/bin/env python3
"""設定用の乱数ツール。

使い方:
    python3 tools/roll.py                      全テーブルを1回ずつ引く
    python3 tools/roll.py --prefix SF          接頭辞で絞って引く
    python3 tools/roll.py --table FT/魔法の源 --n 3
    python3 tools/roll.py --num 0.6 1.6 --step 0.05 --label 重力
    python3 tools/roll.py --seed 12345         シードを指定して再現

引いた目は worlds/<宇宙名>/rolls.md に記録すること。詳しくは core/principles.md。
"""
import argparse
import json
import os
import random

TABLES = os.path.join(os.path.dirname(__file__), "tables.json")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--table", action="append", help="引くテーブル名（複数可）")
    p.add_argument("--prefix", help="この接頭辞で始まるテーブルだけ引く")
    p.add_argument("--n", type=int, default=1, help="各テーブルから引く個数")
    p.add_argument("--num", nargs=2, type=float, metavar=("MIN", "MAX"), help="数値を振る")
    p.add_argument("--step", type=float, default=1.0, help="数値の刻み")
    p.add_argument("--label", default="値", help="数値の見出し")
    p.add_argument("--seed", type=int, help="乱数シード（省略時は自動生成して表示）")
    p.add_argument("--list", action="store_true", help="テーブル名の一覧")
    args = p.parse_args()

    tables = json.load(open(TABLES, encoding="utf-8"))
    if args.list:
        for name in tables:
            print(f"{name}\t({len(tables[name])})")
        return

    seed = args.seed if args.seed is not None else random.randrange(10**9)
    rng = random.Random(seed)
    print(f"seed = {seed}")

    if args.num:
        lo, hi = args.num
        steps = int(round((hi - lo) / args.step))
        val = round(lo + rng.randint(0, steps) * args.step, 6)
        print(f"{args.label}: {val}  （範囲 {lo}〜{hi} / 刻み {args.step}）")
        return

    names = args.table or [n for n in tables if not args.prefix or n.startswith(args.prefix)]
    for name in names:
        if name not in tables:
            raise SystemExit(f"テーブルがない: {name}")
        picks = rng.sample(tables[name], min(args.n, len(tables[name])))
        print(f"{name}: " + " / ".join(picks))


if __name__ == "__main__":
    main()
