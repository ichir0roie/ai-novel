"""db ファイルを退避し、現在の `schema.py` で作り直した空の db へ値を移す。

スキーマの列順・列追加などを `schema.py` 側で直したあと、既存の db ファイルを
新しいテーブル定義に合わせて作り直すための保守スクリプト。`DEM/claude_interface/`
の執筆用入口とは別枠(db そのものの下地を直す作業)なので、直接実行する。

手順:
1. 対象の db ファイルを `backup/` へタイムスタンプ付きでコピーする
2. バックアップした db を読み取り専用のソースとして開き、テーブルごとの列を
   そのまま反映(reflect)する
3. `DEM.db.schema.create_db` で対象の db ファイルを空の状態に作り直す
   (`schema.py` の宣言順で列が並ぶ)
4. `Base.metadata.sorted_tables`(外部キーの依存順)に沿って、バックアップから
   読み出した行を新しい db へ流し込む。列名が一致する列だけをコピーするので、
   `schema.py` 側で削った列があっても止まらない
"""
import os
import shutil
from datetime import datetime

from sqlalchemy import MetaData, create_engine

from DEM.db.schema import Base, DB_PATH, create_db


def rebuild_db(path=DB_PATH, backup_dir="backup"):
    """`path` の db を退避してから、現行スキーマで作り直して値を戻す。

    戻り値はバックアップ先のパス。
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"db が見つからない: {path}")

    backup_dir = os.path.abspath(backup_dir)
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(os.path.basename(path))[0]
    backup_path = os.path.join(backup_dir, f"{base_name}_{stamp}.db")
    shutil.copy2(path, backup_path)

    old_engine = create_engine(f"sqlite:///{backup_path}", future=True)
    old_meta = MetaData()
    old_meta.reflect(bind=old_engine)

    new_engine = create_db(path)

    with old_engine.connect() as old_conn, new_engine.begin() as new_conn:
        new_conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        for table in Base.metadata.sorted_tables:
            if table.name not in old_meta.tables:
                continue
            old_table = old_meta.tables[table.name]
            new_columns = {c.name for c in table.columns}
            common_columns = [
                c.name for c in old_table.columns if c.name in new_columns
            ]
            if not common_columns:
                continue
            rows = old_conn.execute(old_table.select()).mappings().all()
            if not rows:
                continue
            insert_rows = [{name: row[name] for name in common_columns} for row in rows]
            new_conn.execute(table.insert(), insert_rows)
        new_conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    old_engine.dispose()
    return backup_path


if __name__ == "__main__":
    backup_path = rebuild_db()
    print(f"backup: {backup_path}")
