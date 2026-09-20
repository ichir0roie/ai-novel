# 作業指針(AI 向け)

このリポジトリはラノベの執筆用。コードではなく文章を書く。
ローカル環境での実行の場合、現在のブランチ上で直接作業してよい。

**このファイルはリストラクチャ中の状態を反映している。** `core/` → `IHG/`、
`tools/novel.py` → `DEM/claude_interface/*`、`novels/` の md 群 → `novel.db`
(`DEM/db/schema.py` の SQLAlchemy モデル)という移行の途中にあり、
`DEM/claude_interface/` にはまだ全ての入口が揃っていない。無いものを
あるかのように書かない。足りない入口が要るときは、その場で作者に相談するか、
下の「入口の作り方」に沿って `DEM/claude_interface/` に足す。

## 指示があったときの手順の扱い

作者から手順・方針を変える指示があったら、**その場で該当する `IHG/*.md`(や
このファイル)を直しながら作業する。** 指示を実行するだけで、文書を古いまま
放置しない。

直そうとして、既存の手順と矛盾する・情報が足りないと分かったら、
**その場で作者に相談する。** 憶測で決めない。

## 執筆作業は DEM/claude_interface/* 越しにしか行わない

**db(`novel.db`)を直に触らない。読むのも書くのも `DEM/claude_interface/` 配下の
スクリプトを通す。** `DEM.db.schema` を直接 import して読み書きする、`sqlite3` で
`novel.db` を直接開く、あとから export される想定の md を手で作る——どれもしない。
(`DEM/db/` `DEM/randomizer/` `DEM/data_access_logic/` は下地の実装であって、
Claude が執筆作業として直接呼ぶ入口ではない。`DEM/claude_interface/` がその薄い
呼び出し面になる)

### 入口の作り方

`DEM/claude_interface/<領域>/<動詞_対象>.py` に一つ、**一つの呼び出しクラスだけ**を
置く(`DEM/claude_interface/readme.md`)。ランダム生成の一対
(`create_random_character.py` / `commit_character.py`)が現状唯一の実例で、
パターンは次の通り:

- 呼び出し可能なクラスとして書く(CLI 引数のパースはしない。`if __name__ ==
  "__main__"` も置かない。Claude が import して `<クラス>(...).run()` を呼ぶ)
- 各ファイルのクラスは、その領域の基底クラス(`<領域>/_base.py`)を継ぐ。
  領域をまたいで共通する処理(db セッションを開いて渡す・「確定する」系の
  実在確認とスキーマ列チェック)は、さらに上位の `DEM/claude_interface/_base.py`
  に置く。ファイル固有の処理だけをそのクラスに書き、共通の部分は基底へ寄せる
- **「作る」と「db へ確定する」を別ファイルに分ける。** 「作る」側
  (`DEM/randomizer/` の `factory.DictFactory` 等)は db に一切触れず、
  素の辞書 / JSON を返すだけにする。db を触るのは「確定する」側の入口だけに絞る
- 辞書 / JSON で受け渡しする理由は、Bash 呼び出しをまたいでも(＝プロセスが
  切り替わっても)中身を運べるから。SQLAlchemy のオブジェクトや session を
  戻り値にすると、次の呼び出しでは中身が失われる(session が切れているため)
- 実在レコードを指す欄(id)は、確定する側の入口が呼び出し時に db に実在するか
  確かめ、無ければ分かりやすい例外を投げる(SQL を組み立てて確かめない。
  `session.get(Model, id)` のように ORM 越しに引く。基底クラスの
  `check_exists` がこれをやる)。スキーマに無い欄が混ざっていたら、それも
  確定する側の入口で止める(`check_columns`)
- 「作る」側だけを何度呼んでもデータは増えない。db に触れるのは「確定する」側の
  入口を呼んだときだけ

### 現状ある入口

| したいこと                           | 使う入口                                                                                                                                                                                                                                                         |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ランダムな人物の下書きを作る         | `DEM.claude_interface.randomizer.create_random_character.CreateRandomCharacter(...).run()`(db には触れない。辞書を返すだけ)                                                                                                                                      |
| 作った下書きを db へ確定する         | `DEM.claude_interface.randomizer.commit_character.CommitCharacter(<辞書かJSON>).run()`(id の実在確認をしてから書き込む)                                                                                                                                          |
| 作品の一覧と未同期の有無を見る       | `DEM.claude_interface.story.list_stories.ListStories().run()`                                                                                                                                                                                                    |
| モード 2 の材料を一度に出す          | `DEM.claude_interface.story.start_story.StartStory(<作品id>, time=None).run()`(同期の確認・直前の話・断面・顔ぶれ。未同期の話があれば止まる)                                                                                                                     |
| 未同期の話を並べる(2-0)              | `DEM.claude_interface.story.list_unsynced_episodes.ListUnsyncedEpisodes(<作品id>).run()`                                                                                                                                                                         |
| 直前の N 話を読む(2-1)               | `DEM.claude_interface.story.read_episodes.ReadEpisodes(<作品id>, count=10, before=None).run()`                                                                                                                                                                   |
| 顔ぶれを取る(2-3)                    | `DEM.claude_interface.story.read_cast.ReadCast(<作品id>, time=None).run()`(立つ場所の一つ上の配下に居る人物・個体と直近の出来事)                                                                                                                                 |
| 断面を取る(2-3)                      | `DEM.claude_interface.story.read_brief.ReadBrief(<場所id>, <時刻>, reach=60).run()`(`full=True` を付けない)                                                                                                                                                      |
| 喋る人物を一件読む(2-3)              | `DEM.claude_interface.story.read_character.ReadCharacter(<人物id>, time=None).run()`(口調・性格・技・情動・直近の行動)                                                                                                                                           |
| 人物を軸にその時刻の周辺を読む       | `DEM.claude_interface.story.read_surroundings.ReadSurroundings(<人物id>, <時刻>, reach=60).run()`(同じ居場所に居合わせる人物・個体と、`reach` 年ぶんの直近の出来事。作品の場所ではなく**人物**を軸にする点が `read_cast` と違う。展開の検討材料を広げるのに使う) |
| 出来事を引く                         | `DEM.claude_interface.story.read_events.ReadEvents(time=…).run()` / `ReadEvents(record_id=…).run()`                                                                                                                                                              |
| 出来事の `text` の書き方             | 要約(「〜という出来事があった」)で済ませない。**軽い小説として 1000 文字程度**で、その場のキャラクターの思考・行動・(その出来事が及ぼす)影響を場面として書く(`IHG/chronicle.md`「出来事の text は場面で書く」)                                              |
| 本文を db へ確定する(2-4)            | `DEM.claude_interface.story.commit_episode.CommitEpisode(<辞書かJSON>).run()`(字数を数えて入れる。`synced` は必ず下りる)                                                                                                                                         |
| 同期フラグを立てる(3-3)              | `DEM.claude_interface.story.set_episode_synced.SetEpisodeSynced(<作品id>, <話数>).run()`                                                                                                                                                                         |
| db の本文を md へ書き出す            | `DEM.claude_interface.sync.export_db.ExportDb().run()`(`worlds/` をまるごと作り直す。読む専用の写しであって、md を直しても db には戻らない)                                                                                                                      |
| 場所を一覧で見る                     | `DEM.claude_interface.world.list_places.ListPlaces(kind=None).run()`(`kind="村"` のように絞れる。db には触れない)                                                                                                                                                |
| ランダムな場所の下書きを作る         | `DEM.claude_interface.randomizer.create_random_place.CreateRandomPlace(kind="大陸", ...).run()`(db には触れない。`name` は仮の値のまま返る。固有名詞は `IHG/naming.md` の「固有名詞の作り方」に沿って手順で決めてから `CommitPlace` に渡す)                      |
| 作った場所の下書きを db へ確定する   | `DEM.claude_interface.randomizer.commit_place.CommitPlace(<辞書かJSON>).run()`(`parent_id` の実在確認をしてから書き込む)                                                                                                                                         |
| 既にある場所の欄を後から直す         | `DEM.claude_interface.randomizer.update_place.UpdatePlace(<id を含む辞書かJSON>).run()`(渡した欄だけ上書きする。`area` を直すときは `CommitPlace` と同じ、親未満・兄弟の合計が親を超えないの制約を確かめる)                                                       |
| 誤って確定した場所を消す             | `DEM.claude_interface.randomizer.delete_place.DeletePlace(<場所id>).run()`(子の場所が残っていると止まる)                                                                                                                                                         |
| 種別(系統)を一覧で見る               | `DEM.claude_interface.world.list_kinds.ListKinds().run()`(`kind_id` に渡す id を拾う。db には触れない)                                                                                                                                                           |
| 個体(群)を一覧で見る                 | `DEM.claude_interface.world.list_objects.ListObjects(kind=None).run()`(`belong_id` に渡す id を拾う。db には触れない)                                                                                                                                            |
| 語をキーワードで検索する             | `DEM.claude_interface.world.search_terms.SearchTerms(<キーワード>).run()`(`term.text` にキーワードを含む語を返す。db には触れない)                                                                                                                               |
| ランダムな出来事の下書きを作る       | `DEM.claude_interface.randomizer.create_random_event.CreateRandomEvent(...).run()`(db には触れない。辞書を返すだけ)                                                                                                                                              |
| 作った出来事の下書きを db へ確定する | `DEM.claude_interface.randomizer.commit_event.CommitEvent(<辞書かJSON>).run()`(`place_id` `parent_event_id` と、`character_ids` `object_ids`(人物・個体の id のリスト。多対多で何人・何個体でも渡せる)の実在確認をしてから書き込む。出来事が人物の情動・技を動かしたときは、同じ呼び出しに `character_drives`(`[{character_id, text, level, start?, end?}]`)`character_skills`(`[{character_id, skill_id, level, object_id?}]`)を乗せると、`CharacterEmotion`(情動)`CharacterSkill`(技)もまとめて一件ずつ確定する) |
| 人物を一覧で見る                     | `DEM.claude_interface.world.list_characters.ListCharacters().run()`(名前・説明・技の id・情動の件数まで一括で見渡す。db には触れない)                                                                                                                            |
| 既にある人物の欄を後から直す         | `DEM.claude_interface.randomizer.update_character.UpdateCharacter(<id を含む辞書かJSON>).run()`(渡した欄だけ上書きする。`text` の書き直しなどに使う)                                                                                                            |
| 技(能力)そのものを db へ確定する      | `DEM.claude_interface.randomizer.commit_skill.CommitSkill(<辞書かJSON>).run()`(`Skill` のカタログ本体を一件作る。`name` `effect` `text` は必須。ランダム生成の対はまだ無く、内容は手で決める)                                                                   |
| 人物に技を持たせる(出来事に紐づかない場合) | `DEM.claude_interface.randomizer.commit_character_skill.CommitCharacterSkill(<辞書かJSON>).run()`(`character_id` `skill_id`(あれば `object_id`)の実在確認をしてから `CharacterSkill` を一件足す。出来事の結果としての付与は `commit_event` の `character_skills` を使う) |
| 人物に情動を持たせる(出来事に紐づかない場合) | `DEM.claude_interface.randomizer.commit_character_drive.CommitCharacterDrive(<辞書かJSON>).run()`(`character_id` の実在確認をしてから `CharacterEmotion` を一件足す。出来事の結果としての付与は `commit_event` の `character_drives` を使う)                     |

上の表にない操作(旧 `tools/novel.py` が持っていた `check` `index` `template`
など)はまだ `DEM/claude_interface/` に無い。必要になった時点で、上の「入口の作り方」に
沿って足す。**無いものを推測で呼び出そうとしない。**

読む側の入口(`read_*` `list_*` `start_story`)の中身は
`DEM/data_access_logic/query.py` にある。引く条件は**時刻とレコードの id
だけ**で表し、**SQL は組み立てない。** 引き方が足りなければ `query.py` に
関数を足して、`DEM/claude_interface/story/` に一つ入口を被せる。

## まず、どのモードかを決める

作業は三つに分かれている。**一度に一つだけやる**(`IHG/workflow.md`)。

| モード               | 何をするか                 | 触っていいところ                      |
| -------------------- | -------------------------- | ------------------------------------- |
| **1 世界観構成**     | 世界を作る・直す           | 場所・種別・個体・人物・語のレコード  |
| **2 ストーリー生成** | 本文を書く                 | 話(story / episode)のレコード**だけ** |
| **3 世界観更新**     | 書いた本文を世界の側へ戻す | 場所・種別・個体・人物・語のレコード  |

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
  (`DEM.claude_interface.story.start_story.StartStory(<作品id>).run()` で一度に出る)

## 守ること

- **db を直に開かない**: 上の通り。`DEM/claude_interface/` の入口を通す
- **レコードの型は `DEM/db/schema.py` が一か所で決めている**: 欄を増やしたければ
  `schema.py` を直し、alembic でマイグレーションを一本切る(`DEM/db/alembic/`)
- **参照は id で持つ**: 他のレコードを指す欄には、名前ではなく id を渡す。
  id は呼び出し側(作者・Claude)が事前に db から引いたものだけを使い、
  存在確認は入口側の責任にする
- **設定の一元管理**: 本文で新しい設定(地名・組織・技名・過去の出来事)を作ったら、
  モード 3 で必ず世界の側へ書き戻す。**本文にしか存在しない設定を残さない**
- **用語は日本語として自然に**: 読者は日本人。日本的な漢字(訓読み)・ひらがな・
  カタカナ英語で名づける。音読み二字熟語の造語を重ねない(`IHG/naming.md`)
- **なろう系テンプレを使わない**: 禁止事項の具体リストは `IHG/principles.md`。構造として避ける
- **アバウトな要素は乱数で決める**: `DEM/randomizer/roll.py` を使い、引いた目を記録に残す。
  AI の第一想起で埋めない。**現状 `DEM/randomizer/tables.json` が無く、`roll.py`
  は動かない。** 直すか作者に確認するまでは、`random` で代用しつつシードを
  会話に残す(実施例: `create_random_place` で大陸を作ったとき、固有名詞の
  言語ロールをこの方法で代用した)
- **同じ世界線の中で矛盾しない**: 暦・共通現象・星どうしの関係は星をまたいで一致させる。
  世界線が違えば矛盾してよい(平行世界)
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

- **作っただけで終わらせず、確定する側の入口まで呼んだか確認する**(`create_random_character`
  のような「作る」入口は db に触れない。`commit_character` のような「確定する」
  入口を呼んで初めて db に残る)
- 作業が終わったら、claude webで動作している場合、以下を実施。
  - **その内容でプルリクエストがなければ作成し、リンクを表示する**。
  - すでにあるなら、そのブランチへプッシュしてリンクを示す

## やらないこと

- `novel.db` を `DEM/claude_interface/` を通さずに直接読み書きする
- 頼まれていない話数を勝手に書き足す
- 既存の原稿を「ついでに」推敲して書き換える(指示があったときだけ)
- プロットにない大きな展開の追加(提案は歓迎、無断実装は不可)
- モードをまたいで、本文と設定を同時に書き換える
