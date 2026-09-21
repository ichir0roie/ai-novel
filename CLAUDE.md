# 作業指針

このリポジトリは、AI が自動で世界(`novel.db`)を進めながらラノベを
書かせる仕組みを作るためのもの。

ローカル環境での実行の場合、現在のブランチ上で直接作業してよい。

作業を始める前に、リモートの最新の変更を取り込む

# 関数・モジュール冒頭に長いコメントを書かない

書く前に既存のコードを読み込んで理解し、コメントは「読んでも分からない理由」
(型の癖・回避しているバグ・非自明な制約)がある場合の一行程度に留める。

# 既存のコードの仕様を守る。

現在のタスクの修正のみを行い、関係のない部分の修正は行わない。寄り道しない。

# 「更新」の依頼があった場合
- main ブランチへのコミットを頼まれたときは、深く調査しない
- 変更内容を掘り下げて「なぜ」まで書いた丁寧なメッセージを作らず、diff・変更ファイルの表層だけを見て、端的なメッセージでそのままコミットする
- プッシュ前に、最新の変更を取り込んで、コンフリクトがあれば解消してからpush

# 文字コード

- リポジトリのテキスト(`.py` `.md` `.json` `.yaml` など)はすべて **UTF-8**(BOM 無し)。
  ファイルを開くときは必ず `encoding="utf-8"` を付ける
- `novel.db` の文字列も UTF-8(`create_db` が `PRAGMA encoding='UTF-8'` を打つ)。
  `.gitattributes` で `*.db` はバイナリ扱い
- Windows の python は標準出力が cp932 になるため、日本語を出すコマンドは
  `PYTHONUTF8=1` を付けて実行する(付けないと文字化け・`UnicodeEncodeError` になる)

# 実行環境

- python は **`.venv/Scripts/python.exe`** を使う(`which python` は別の virtualenv を指す)。
  bash なら `PYTHONUTF8=1 .venv/Scripts/python.exe -m ...`
- リポジトリのルートから実行する(`DEM.` から始まる import はルート基準)
- `sqlite3` CLI は入っていない。db を覗くときは python の `sqlite3` モジュールか SQLAlchemy を使う
- `ModuleNotFoundError` など依存不足で実行が失敗したら、まず
  `.venv/Scripts/python.exe -m pip install -r requirements.txt` を試してから調査する

# db への接続

- 実体は **ルートの `novel.db`**(SQLite)。パスは `DEM/db/schema.py` の `DB_PATH`
  で、環境変数 `DEM_DB_PATH` で差し替えられる
- コードから触るときは `from DEM.db.schema import get_session` で `Session` を開く。
  `engine` も同じモジュールにある
- 作業として db を読み書きするときは `DEM/claude_interface/` の入口越しに行う
  (一覧は `DEM/claude_interface/readme.md`)。下地(`DEM/db/` `DEM/data_access_logic/`)を直接呼ぶのは開発・調査のときだけ
- 引き方(`DEM/data_access_logic/query/*.py`)では、外部キーが `NULL` の行を
  「全体に効く」とみなして `or_(X.fk_id.in_(ids), X.fk_id.is_(None))` のように
  無理に拾わない。関係が無い行は「関係が無い」として扱う
- 調査用の読み取り例:

```
PYTHONUTF8=1 .venv/Scripts/python.exe -c "
import sqlite3
c = sqlite3.connect('novel.db')
print(c.execute('select count(*) from character').fetchone())
"
```

# schema の確認方法

- **列の定義は `DEM/db/schema.py` が唯一の正**。列の意味は各 `mapped_column` の `comment=` に書いてある
- モデルから一覧を出す:

```
PYTHONUTF8=1 .venv/Scripts/python.exe -c "
from DEM.db.schema import Base
for t in Base.metadata.sorted_tables:
    print(t.name, [c.name for c in t.columns])
"
```

- 実 db 側の形を見る(`schema.py` と食い違っていないかの確認):

```
PYTHONUTF8=1 .venv/Scripts/python.exe -c "
import sqlite3
c = sqlite3.connect('novel.db')
print([r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")])
print(c.execute('PRAGMA table_info(character)').fetchall())
"
```

- マイグレーションは `DEM/db/alembic/`。コマンド例は `DEM/db/alembic/README` にある。
  今のリビジョン確認は `.venv/Scripts/python.exe -m alembic -c DEM/db/alembic/alembic.ini current`
- `schema.py` を変えたら alembic の `revision --autogenerate` → 内容確認 → `upgrade head` の順。
  `DEM/db/rebuild_db.py`(退避して作り直し)や `DEM/tool/danger/`(世界の消去・再走)は
  データを消す操作なので、頼まれたときだけ使う
