"""db ファイルを退避し、現在の `schema.py` で作り直した空の db へ値を移す保守スクリプト。"""
import decimal
import os
import shutil
from datetime import datetime

from sqlalchemy import MetaData, create_engine, select, text

from db.schema import Base, DB_PATH, create_db


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

    old_engine = create_engine(f"sqlite:///{backup_path}")
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
            rows = old_conn.execute(select(old_table)).mappings().all()
            if not rows:
                continue
            insert_rows = [
                {
                    name: (
                        str(row[name])
                        if isinstance(row[name], decimal.Decimal)
                        else row[name]
                    )
                    for name in common_columns
                }
                for row in rows
            ]
            # `table.insert()` は列の型(StampType 等)を通して値を変換し直すが、
            # ここで運ぶ値は元の db に既に格納済みの生の値(例: Stamp は
            # 年月日を詰めた整数)なので、再変換すると Stamp.parse が
            # 受け付けない形になって落ちる。型変換をかけない生 SQL で流し込む
            # (sqlite3 ドライバは Decimal を直接バインドできないので str にする)。
            columns_sql = ", ".join(f'"{name}"' for name in common_columns)
            placeholders_sql = ", ".join(f":{name}" for name in common_columns)
            insert_stmt = text(
                f'INSERT INTO "{table.name}" ({columns_sql}) '
                f"VALUES ({placeholders_sql})"
            )
            new_conn.execute(insert_stmt, insert_rows)
        new_conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    old_engine.dispose()
    return backup_path


if __name__ == "__main__":
    backup_path = rebuild_db()
    print(f"backup: {backup_path}")
