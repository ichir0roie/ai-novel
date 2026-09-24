# 作業指針

このリポジトリは、AI が自動で世界(`novel.db`)を進めながらラノベを
書かせる仕組みを作るためのもの。

ローカル環境での実行の場合、現在のブランチ上で直接作業してよい。

依頼の冒頭に `term` `plot` などがある場合はテキスト追加の依頼なので、
クラウド環境でも作業用ブランチや PR を作らず、main で直接作業してコミット・プッシュしてよい。
コード修正がある場合は、ブランチを作成する。

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
- コミットは `core/`(このリポジトリ)と世界リポジトリ(my-novel-world)の **両方に同じメッセージで** 行う。
  手順は「環境構築」のとおり `core/` → 世界の順

# 文字コード

- リポジトリのテキスト(`.py` `.md` `.json` `.yaml` など)はすべて **UTF-8**(BOM 無し)。
  ファイルを開くときは必ず `encoding="utf-8"` を付ける
- `novel.db` の文字列も UTF-8(`create_db` が `PRAGMA encoding='UTF-8'` を打つ)。
  `.gitattributes` で `*.db` はバイナリ扱い
- Windows の python は標準出力が cp932 になるため、日本語を出すコマンドは
  `PYTHONUTF8=1` を付けて実行する(付けないと文字化け・`UnicodeEncodeError` になる)

# 環境構築

コード(このリポジトリ `ai-novel-core`)と実データ(`novel.db`・`worlds/`)は別リポジトリに分けている。
実データ側のリポジトリ(private の `my-novel-world`)が、このリポジトリをサブモジュール `core/` として持つ。
コードは `core/` から見た親ディレクトリ(`..`)を世界として読み書きする(環境変数 `DEM_WORLD_DIR` で差し替えられる)。
自分の世界を作るときは、空のリポジトリで `git submodule add https://github.com/ichir0roie/ai-novel-core.git core` する。

```
my-novel-world/
  core/      このリポジトリ(サブモジュール)。python のコマンドはここから実行する
  novel.db
  worlds/
```

git のコマンドは世界リポジトリのルートで打つ。

```
# clone(サブモジュールごと)
git clone --recurse-submodules https://github.com/ichir0roie/my-novel-world.git

# clone 済みで core/ が空のとき
git submodule update --init

# 最新を取り込む(世界と core/ の両方)
git pull --recurse-submodules
git submodule update --init

# コミットは両方のリポジトリに同じメッセージで。core/ 側を先にコミットしてから世界側で参照を更新する
git -C core switch main   # サブモジュールは detached HEAD になっているため
git -C core add -A
git -C core commit -m "<メッセージ>"
git -C core push
git add -A
git commit -m "<メッセージ>"
git push
```

世界リポジトリの VS Code タスク `git push` は、この順で両方に同じメッセージ(日時)でコミットして push する。

# 実行環境

- python は **`.venv/Scripts/python.exe`** を使う(`which python` は別の virtualenv を指す)。
  bash なら `PYTHONUTF8=1 .venv/Scripts/python.exe -m ...`
- このリポジトリ(世界リポジトリの `core/`)のルートから実行する(`DEM.` から始まる import はルート基準)
- `sqlite3` CLI は入っていない。db を覗くときは python の `sqlite3` モジュールか SQLAlchemy を使う
- `ModuleNotFoundError` など依存不足で実行が失敗したら、まず
  `.venv/Scripts/python.exe -m pip install -r requirements.txt` を試してから調査する

# テスト

- `tests/` に pytest のテストがある。
- **回すのは、実装した影響範囲のテストだけを選んで回す。** 全体を回さない
  (`... -m pytest tests/test_foo.py tests/test_bar.py` のようにファイルを指定する)
- テストは `novel.test.db` だけを読み書きする(`tests/conftest.py` が `DEM.tool.test` を先に読んで固定する)。
  本番の `novel.db` には触れない
- db・入口・生成器を変えたら、対応するテストを足すか直してから終える
- プルリクを作る前に必ず、変更に対するテストケースを実装し、影響範囲のテストを回し、
  出たエラーを直してから作る

# db への接続

- 実体は **世界リポジトリ(`..`)の `novel.db`**(SQLite。private リポジトリ `my-novel-world`)。
  コマンドは「環境構築」を見る。パスは `DEM/db/schema.py` の `DB_PATH`
  で、環境変数 `DEM_DB_PATH` で差し替えられる
- コードから触るときは `from DEM.db.schema import get_env_session` で `Session` を開く。
  `engine` も同じモジュールにある
- 作業として db を読み書きするときは `DEM/ai/claude_code/interface/` の入口越しに、
  既存の python コードを呼んで行う。下地(`DEM/db/` `DEM/data_access_logic/`)を
  直接呼んだり、その場限りのスクリプトを書いたりするのは開発・調査のときだけ
- **`DEM/ai/claude_code/interface/readme.md` を操作前のマニュアルとする。**
  操作の前にその「依頼内容 → 呼ぶコード」の対応表を引き、依頼に当たる入口を呼ぶ
- 対応する入口が無ければ、readme の「作り方」に沿って入口を新しく作ってから行う。
  **足したら同じ作業のうちに readme の対応表へ行を足す**(表に無い入口は次から見えない)
- 各作業前に、`DEM/tool/markdown/sync_db.py`を実行する。
  同期の向きと順序は「md と db の同期」を見る
- 引き方(`DEM/data_access_logic/query/*.py`)では、外部キーが `NULL` の行を
  「全体に効く」とみなして `or_(X.fk_id.in_(ids), X.fk_id.is_(None))` のように
  無理に拾わない。関係が無い行は「関係が無い」として扱う
- 調査用の読み取り例:

```
PYTHONUTF8=1 .venv/Scripts/python.exe -c "
import sqlite3
c = sqlite3.connect('../novel.db')
print(c.execute('select count(*) from character').fetchone())
"
```

# md と db の同期(import / export)

`import_db` は md を db へ無条件に上書きし、`export_db` は `worlds/` をまるごと
消して db から書き直す。突き合わせはしないので、**後に回した向きが丸ごと勝つ**。
だから一つの作業のあいだ、md と db のどちらが正かを決めて動かす。

- **手で md を直すなら、直し終えてから `import_db` を回す。** 直しかけのまま
  db を触る作業を始めない
- **db を触る作業は `import_db` → 入口越しの変更 → `export_db` の一続きで回し、
  その間 `worlds/` を触らない。** 変更したあとに `import_db` を挟むと、md 側の
  古い内容でその変更が消える(`export_db` の直前に `import_db` を回してはいけない)
- 途中で md を直したくなったら、挟まずに区切る。いったん `export_db` で db を
  md へ落とし、そこから直して `import_db` する(＝次の作業の頭にする)
- 手直しが残っているかは `git -C .. status --short worlds/` で見る
- `ExportDb` は、前回の同期(`.markdown_sync` の mtime)より後に書かれた md が
  あれば止まる。止まったら `ImportDb` で取り込んでから db 側の変更をやり直す。
  md を捨ててよいと分かっているときだけ `ExportDb(force=True)`

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
c = sqlite3.connect('../novel.db')
print([r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")])
print(c.execute('PRAGMA table_info(character)').fetchall())
"
```

- マイグレーションは `DEM/db/alembic/`。コマンド例は `DEM/db/alembic/README` にある。
  今のリビジョン確認は `.venv/Scripts/python.exe -m alembic -c DEM/db/alembic/alembic.ini current`
- `schema.py` を変えたら alembic の `revision --autogenerate` → 内容確認 → `upgrade head` の順。
  `DEM/db/rebuild_db.py`(退避して作り直し)や `DEM/tool/danger/`(世界の消去・再走)は
  データを消す操作なので、頼まれたときだけ使う
