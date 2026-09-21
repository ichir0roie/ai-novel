# 作業指針(AI 向け)

このリポジトリは、AI が自動で世界(`novel.db`)を進めながらラノベを
書かせる仕組みを作るためのもの。**Claude がここで書くのは文章ではなく
コード。** 出来事・人物・個体・場所も、本文(`episode`)も、Claude が
対話の中で直接生成することはしない。生成は `DEM/local_ai/`(常駐ループ)
が担い、Claude の仕事はその生成の仕組み(`DEM/local_ai/`
`DEM/claude_interface/` `DEM/data_access_logic/` `DEM/db/`)を
開発・保守すること。
ローカル環境での実行の場合、現在のブランチ上で直接作業してよい。

**作業を始める前に、リモートの最新の変更を取り込む**(`git pull`)。
`novel.db` はバイナリで直接 git 管理下にあるため、取り込みが遅れるほど、
自分の変更と食い違って上書きしてしまう・逆に取り込んだ側の db 更新に
気づかず古いスキーマで作業してしまう、といった事故につながる。

**移行は終わっている。** 方針・設計根拠は `IHG/`、仕組みは `DEM/`、
記録と本文は `novel.db`(`DEM/db/schema.py` の SQLAlchemy モデル)にある。
旧 `core/` `tools/novel.py` `novels/` の md 群はもう無い。

**`DEM/claude_interface/` にはまだ全ての入口が揃っていない**
(語 `term` を確定する入口が無い、など)。無いものを
あるかのように書かない。足りない入口が要るときは、その場で作者に相談するか、
`DEM/claude_interface/readme.md`「作り方」に沿って `DEM/claude_interface/` に足す。

## 指示があったときの手順の扱い

作者から手順・方針を変える指示があったら、**その場で該当する `IHG/*.md`(や
このファイル)を直しながら作業する。** 指示を実行するだけで、文書を古いまま
放置しない。

直そうとして、既存の手順と矛盾する・情報が足りないと分かったら、
**その場で作者に相談する。** 憶測で決めない。

## Claude はもう物語を直接生成しない

出来事(`event`)・人物(`character`)・個体(`object`)・場所(`location`)・
筋書き(`plot`)・本文(`episode`)——**このどれも、Claude が対話の中で
`CreateRandom*`/`Commit*` のような入口を呼んで直接作ることはしない。**
生成は `DEM/local_ai/time_keeper/` の常駐ループに一本化している。
「イベントを起こして」「キャラを足して」と頼まれたら、Claude 自身が
書き込むのではなく、**常駐ループ側(生成の確率・条件・`Plot`)を直す**
仕事として受け取る。詳しくは `IHG/workflow.md`。

常駐ループの起動・停止だけは、運用タスクとして
`DEM.local_ai.time_keeper.main.claude_main()` を直接呼んでよい
(生成そのものはローカル AI が行うため)。

## db は DEM/claude_interface/* 越しにしか触らない

**db(`novel.db`)を直に触らない。読むのも書くのも `DEM/claude_interface/` 配下の
スクリプトを通す。** `DEM.db.schema` を直接 import して読み書きする、`sqlite3` で
`novel.db` を直接開く、あとから export される想定の md を手で作る——どれもしない。
(`DEM/db/` `DEM/randomizer/` `DEM/data_access_logic/` は下地の実装であって、
Claude が直接呼ぶ入口ではない。`DEM/claude_interface/` がその薄い呼び出し面になる)

**入口の実装パターン(呼び出しクラスの書き方・「作る」と「確定する」の分離・
基底クラスの継ぎ方)も、今ある入口の一覧も `DEM/claude_interface/readme.md`
にまとめてある。** 新しい入口を足すときはそこを見る。
上の表にない操作(語 `term` の確定、整合チェック、用語索引の書き出しなど)は
まだ `DEM/claude_interface/` に無い。必要になった時点で、
`DEM/claude_interface/readme.md`「作り方」に沿って足す。
**無いものを推測で呼び出そうとしない。**

## 書く前に必ず読む

- `IHG/principles.md` — 何のために書くか。迷ったらこれが最優先
- `IHG/workflow.md` — **進め方。Claude はもう本文・出来事・人物などを直接生成しない**
- `IHG/chronicle.md` — 記録の取り方と、話を尽きさせない仕組み
- `IHG/naming.md` — 用語と名づけの基準(`ai_instructions/naming.py` の正本)
- `IHG/README.md` — IHG の索引と、IHG / DEM の分担・`IHG/ai_instructions/` の位置づけ
- `DEM/claude_interface/readme.md` — 今ある入口の一覧と、新しい入口の作り方

## 守ること

生成の基準(用語の自然さ・なろう系テンプレ回避・出来事の書き方・数を
本文に出さないこと・世界線の一貫性、等)は `IHG/*.md` にあり、常駐ループへは
`IHG/ai_instructions/*.py` の定数として渡っている。**基準を変えたいときは、
まず正本の `IHG/*.md` を直し、対応する `ai_instructions/*.py` を揃えて直す**
(どちらが正本かは `IHG/README.md`「常駐ループへ渡す基準」)。

- **db を直に開かない**: 上の通り。`DEM/claude_interface/` の入口を通す
- **レコードの型は `DEM/db/schema.py` が一か所で決めている**: 欄を増やしたければ
  `schema.py` を直し、alembic でマイグレーションを一本切る(`DEM/db/alembic/`)
- **参照は id で持つ**: 他のレコードを指す欄には、名前ではなく id を渡す。
  id は呼び出し側(作者・Claude)が事前に db から引いたものだけを使い、
  存在確認は入口側の責任にする
- **関数・モジュール冒頭に長いコメントを書かない**: 処理を実装するたびに
  10行を超えるようなコメント・docstring を書きがちだが、そのほとんどは
  コードを読めば分かる内容の言い換えでしかない。書く前に既存のコードを
  読み込んで理解し、コメントは「読んでも分からない理由」(型の癖・
  回避しているバグ・非自明な制約)がある場合の一行程度に留める

## 「更新」の依頼があった場合
- main ブランチへのコミットを頼まれたときは、深く調査しない
- 変更内容を掘り下げて「なぜ」まで書いた丁寧なメッセージを作らず、diff・変更ファイルの表層だけを見て、端的なメッセージでそのままコミットする
- プッシュ前に、最新の変更を取り込んで、コンフリクトがあれば解消してからpush

## やらないこと

- `novel.db` を `DEM/claude_interface/` を通さずに直接読み書きする
- Claude 自身が `Commit*` 系の入口を呼んで、出来事・人物・個体・場所・本文を
  対話の中で直接 db に書き込む(常駐ループに任せる)
- `DEM/claude_interface/world/advance_time.py` のような、常駐ループを介さず
  Claude 自身が世界を進めるコードを新設する
