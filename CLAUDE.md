# 作業指針

## ローカル環境
コード修正であっても常に現在のブランチ(主に main)上で直接作業する。


# コーディング規約

コードを読んで内容を理解すること。
コードを読んでも分からない理由のみコメントにする。

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
コードは環境変数 `DEM_WORLD_DIR` で渡されたディレクトリを世界として読み書きする(未設定なら import で止まる)。
python・pytest・alembic は世界リポジトリのルートを cwd にし、`DEM_WORLD_DIR` にそのルートを、
`PYTHONPATH` に `<ルート>/core` を渡して動かす。
md と db の同期(`import_db` / `export_db`)が使う `novel.db` と `worlds/` は、それぞれ `DEM_NOVEL_DB_PATH` / `DEM_WORLDS_DIR` でも個別に差し替えられる。
自分の世界を作るときは、空のリポジトリで `git submodule add https://github.com/ichir0roie/ai-novel-core.git core` する。


git のコマンドは世界リポジトリのルートで打つ。

```
# clone(サブモジュールごと)
git clone --recurse-submodules https://github.com/ichir0roie/my-novel-world.git

# clone 済みで core/ が空のとき
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

# テスト

- `tests/` に pytest のテストがある。世界リポジトリのルートから `python -m pytest core/tests` で回す。
- テストは `novel.test.db` だけを読み書きする(`tests/conftest.py` が `DEM.tool.test` を先に読んで固定する)。
  本番の `novel.db` には触れない
- db・入口・生成器を変えたら、対応するテストを足すか直してから終える
- プルリクを作る前に必ず、変更に対するテストケースを実装し、影響範囲のテストを回し、
  出たエラーを直してから作る

# db への接続

- コードから触るときは `from DEM.db.schema import get_env_session` で `Session` を開く。
  `engine` も同じモジュールにある
- 作業として db を読み書きするときは `DEM/ai/claude_code/interface/` の入口越しに、
  既存の python コードを呼んで行う。
- **`DEM/ai/claude_code/interface/readme.md` を操作前のマニュアルとする。**
  操作の前にその「依頼内容 → 呼ぶコード」の対応表を引き、依頼に当たる入口を呼ぶ
- 対応する入口が無ければ、readme の「作り方」に沿って入口を新しく作ってから行う。
  **足したら同じ作業のうちに readme の対応表へ行を足す**(表に無い入口は次から見えない)
- **読み取り(`select`)だけなら入口を通さなくてよい。** python の `sqlite3` や SQLAlchemy で
  好きに覗いてよい。読むだけなら `import_db` / `export_db` も回さなくてよい。
  書き込み(`insert` `update` `delete`)は必ず入口越しに行う
- 調査用の読み取り例(世界リポジトリのルートで `.venv/bin/python` を使う。`core/` は `.venv` の場所を持たない):

```
.venv/bin/python -c "
import sqlite3
from DEM.db.schema import NOVEL_DB_PATH
c = sqlite3.connect(NOVEL_DB_PATH)
print(c.execute('select count(*) from character').fetchone())
"
```

# md と db の同期(import / export)

`import_db` は md を db へ無条件に上書きする。
`export_db` は `worlds/` をまるごと消して db から書き直す。
`sync_db`は、import_db,export_dbの順に実行する。

worlds/**/*.markdownファイルは直接変更しない。
db を修正する作業は、import_db → 入口越しの修正 → export_db の順で回す(ローカルでもクラウドでも同じ)。
修正の後に import_db(sync_db)を回すと、md の古い内容で修正が消える。
修正したレコードが巻き戻った場合は、importされたものを優先する。ユーザの直接編集を優先する。


# schema の確認方法

- **列の定義は `DEM/db/schema.py` が唯一の正**。

- マイグレーションは `DEM/db/alembic/`。コマンド例は `DEM/db/alembic/README` にある。
- `schema.py` を変えたら alembic の `revision --autogenerate` → 内容確認 → `upgrade head` の順。
