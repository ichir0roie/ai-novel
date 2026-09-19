# 作業指針（AI 向け）

このリポジトリはラノベの執筆用。コードではなく文章を書く。
ローカル環境での実行の場合、現在のブランチ上で直接作業してよい。

**このファイルはリストラクチャ中の状態を反映している。** `core/` → `IHG/`、
`tools/novel.py` → `DEM/claude_interface/*`、`novels/` の md 群 → `novel.db`
（`DEM/db/schema.py` の SQLAlchemy モデル）という移行の途中にあり、
`DEM/claude_interface/` にはまだ全ての入口が揃っていない。無いものを
あるかのように書かない。足りない入口が要るときは、その場で作者に相談するか、
下の「入口の作り方」に沿って `DEM/claude_interface/` に足す。

## 指示があったときの手順の扱い

作者から手順・方針を変える指示があったら、**その場で該当する `IHG/*.md`（や
このファイル）を直しながら作業する。** 指示を実行するだけで、文書を古いまま
放置しない。

直そうとして、既存の手順と矛盾する・情報が足りないと分かったら、
**その場で作者に相談する。** 憶測で決めない。

## 執筆作業は DEM/claude_interface/* 越しにしか行わない

**db（`novel.db`）を直に触らない。読むのも書くのも `DEM/claude_interface/` 配下の
スクリプトを通す。** `DEM.db.schema` を直接 import して読み書きする、`sqlite3` で
`novel.db` を直接開く、あとから export される想定の md を手で作る——どれもしない。
（`DEM/db/` `DEM/randomizer/` `DEM/data_access_logic/` は下地の実装であって、
Claude が執筆作業として直接呼ぶ入口ではない。`DEM/claude_interface/` がその薄い
呼び出し面になる）

### 入口の作り方

`DEM/claude_interface/<領域>/<動詞_対象>.py` に一つ、**一つの呼び出し機能だけ**を
置く（`DEM/claude_interface/readme.md`）。ランダム生成の一対
（`create_random_character.py` / `commit_character.py`）が現状唯一の実例で、
パターンは次の通り:

- 呼び出し可能な関数として書く（CLI 引数のパースはしない。Claude が import して呼ぶ）
- **「作る」と「db へ確定する」を別ファイルに分ける。** 「作る」側
  （`DEM/randomizer/` の `factory.DictFactory` 等）は db に一切触れず、
  素の辞書 / JSON を返すだけにする。db を触るのは「確定する」側の入口だけに絞る
- 辞書 / JSON で受け渡しする理由は、Bash 呼び出しをまたいでも（＝プロセスが
  切り替わっても）中身を運べるから。SQLAlchemy のオブジェクトや session を
  戻り値にすると、次の呼び出しでは中身が失われる（session が切れているため）
- 実在レコードを指す欄（id）は、確定する側の入口が呼び出し時に db に実在するか
  確かめ、無ければ分かりやすい例外を投げる（SQL を組み立てて確かめない。
  `session.get(Model, id)` のように ORM 越しに引く）。スキーマに無い欄が
  混ざっていたら、それも確定する側の入口で止める
- 「作る」側だけを何度呼んでもデータは増えない。db に触れるのは「確定する」側の
  入口を呼んだときだけ

### 現状ある入口

| したいこと                     | 使う入口                                                                              |
| ------------------------------ | -------------------------------------------------------------------------------------- |
| ランダムな人物の下書きを作る   | `DEM.claude_interface.randomizer.create_random_character.create_random_character(...)`（db には触れない。辞書を返すだけ） |
| 作った下書きを db へ確定する   | `DEM.claude_interface.randomizer.commit_character.commit_character(<辞書かJSON>)`（id の実在確認をしてから書き込む） |
| 作品の一覧と未同期の有無を見る | `DEM.claude_interface.story.list_stories.list_stories()` |
| モード 2 の材料を一度に出す   | `DEM.claude_interface.story.start_story.start_story(<作品id>, time=None)`（同期の確認・直前の話・断面・顔ぶれ。未同期の話があれば止まる） |
| 未同期の話を並べる（2-0）     | `DEM.claude_interface.story.list_unsynced_episodes.list_unsynced_episodes(<作品id>)` |
| 直前の N 話を読む（2-1）      | `DEM.claude_interface.story.read_episodes.read_episodes(<作品id>, count=10, before=None)` |
| 顔ぶれを取る（2-3）           | `DEM.claude_interface.story.read_cast.read_cast(<作品id>, time=None)`（立つ場所の一つ上の配下に居る人物・個体と直近の出来事） |
| 断面を取る（2-3）             | `DEM.claude_interface.story.read_brief.read_brief(<場所id>, <時刻>, reach=60)`（`full=True` を付けない） |
| 喋る人物を一件読む（2-3）     | `DEM.claude_interface.story.read_character.read_character(<人物id>, time=None)`（口調・性格・技・情動・直近の行動） |
| 出来事を引く                   | `DEM.claude_interface.story.read_events.read_events(time=…)` / `read_events(record_id=…)` |
| 本文を db へ確定する（2-4）   | `DEM.claude_interface.story.commit_episode.commit_episode(<辞書かJSON>)`（字数を数えて入れる。`synced` は必ず下りる） |
| 同期フラグを立てる（3-3）     | `DEM.claude_interface.story.set_episode_synced.set_episode_synced(<作品id>, <話数>)` |
| db の本文を md へ書き出す      | `DEM.claude_interface.sync.export_db.export_db()`（`worlds/` をまるごと作り直す。読む専用の写しであって、md を直しても db には戻らない） |

上の表にない操作（旧 `tools/novel.py` が持っていた `check` `index` `template`、
世界の側（場所・種別・個体・語）を確定する入口など）はまだ
`DEM/claude_interface/` に無い。必要になった時点で、上の「入口の作り方」に
沿って足す。**無いものを推測で呼び出そうとしない。**

読む側の入口（`read_*` `list_*` `start_story`）の中身は
`DEM/data_access_logic/query.py` にある。引く条件は**時刻とレコードの id
だけ**で表し、**SQL は組み立てない。** 引き方が足りなければ `query.py` に
関数を足して、`DEM/claude_interface/story/` に一つ入口を被せる。

## まず、どのモードかを決める

作業は三つに分かれている。**一度に一つだけやる**（`IHG/workflow.md`）。

| モード               | 何をするか                 | 触っていいところ                    |
| -------------------- | --------------------------- | ------------------------------------ |
| **1 世界観構成**     | 世界を作る・直す            | 場所・種別・個体・人物・語のレコード |
| **2 ストーリー生成** | 本文を書く                  | 話（story / episode）のレコード**だけ** |
| **3 世界観更新**     | 書いた本文を世界の側へ戻す  | 場所・種別・個体・人物・語のレコード |

**モード 2 のあいだは世界の側を一行も書き換えない。**
本文を書く途中で新しい設定が生まれたら、メモに控えてモード 3 まで持ち越す。
**モード 3 のあいだは本文を書き換えない。**

## 書く前に必ず読む

- `IHG/principles.md` — 何のために書くか。迷ったらこれが最優先
- `IHG/workflow.md` — **三つのモードと、それぞれの手順**
- `IHG/chronicle.md` — 記録の取り方と、話を尽きさせない仕組み
- `IHG/writing-style.md` — 文体の方針
- `IHG/naming.md` — 用語と名づけの基準
- `IHG/structure.md` / `IHG/characters.md` / `IHG/dialogue.md` / `IHG/checklist.md`
  — 構成・キャラ造形・会話文のテクニックと、書き上げたあとのチェックリスト
- 対象作品の直前の話・企画・その作品が立つ世界線の断面
  （`DEM.claude_interface.story.start_story.start_story(<作品id>)` で一度に出る）

## 守ること

- **db を直に開かない**: 上の通り。`DEM/claude_interface/` の入口を通す
- **レコードの型は `DEM/db/schema.py` が一か所で決めている**: 欄を増やしたければ
  `schema.py` を直し、alembic でマイグレーションを一本切る（`DEM/db/alembic/`）
- **参照は id で持つ**: 他のレコードを指す欄には、名前ではなく id を渡す。
  id は呼び出し側（作者・Claude）が事前に db から引いたものだけを使い、
  存在確認は入口側の責任にする
- **設定の一元管理**: 本文で新しい設定（地名・組織・技名・過去の出来事）を作ったら、
  モード 3 で必ず世界の側へ書き戻す。**本文にしか存在しない設定を残さない**
- **用語は日本語として自然に**: 読者は日本人。日本的な漢字（訓読み）・ひらがな・
  カタカナ英語で名づける。音読み二字熟語の造語を重ねない（`IHG/naming.md`）
- **なろう系テンプレを使わない**: 禁止事項の具体リストは `IHG/principles.md`。構造として避ける
- **アバウトな要素は乱数で決める**: `DEM/randomizer/roll.py` を使い、引いた目を記録に残す。
  AI の第一想起で埋めない
- **同じ世界線の中で矛盾しない**: 暦・共通現象・星どうしの関係は星をまたいで一致させる。
  世界線が違えば矛盾してよい（平行世界）
- **既存設定の優先**: 世界の側にあるレコードと食い違う本文は書かない。
  変えたいときは先に設定側を直す
- **作品は世界線をまたがない**: どの世界線に立つ作品かは作品のレコードに持たせる。
  **複数の世界線をまたぐ作品は作らない**
- **文体の一貫性**: 途中から語り口を変えない。一人称/三人称、地の文の温度、
  句読点の癖を作品内で揃える
- **要約で済ませない**: 「〜という展開があった」で流さず、場面として書く。
  ダイジェストは読者が飛ばす
- **数を本文に出さない**: 記録の数は作者だけが見る目盛りであって、作中の誰も知らない

## 作業の締め

- **作っただけで終わらせず、確定する側の入口まで呼んだか確認する**（`create_random_character`
  のような「作る」入口は db に触れない。`commit_character` のような「確定する」
  入口を呼んで初めて db に残る）
- 作業が終わったら、claude webで動作している場合、以下を実施。
  - **その内容でプルリクエストがなければ作成し、リンクを表示する**。
  - すでにあるなら、そのブランチへプッシュしてリンクを示す

## やらないこと

- `novel.db` を `DEM/claude_interface/` を通さずに直接読み書きする
- 頼まれていない話数を勝手に書き足す
- 既存の原稿を「ついでに」推敲して書き換える（指示があったときだけ）
- プロットにない大きな展開の追加（提案は歓迎、無断実装は不可）
- モードをまたいで、本文と設定を同時に書き換える
