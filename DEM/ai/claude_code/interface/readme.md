claude が db を触るときに呼ぶ入口を置く場所。**操作前にこの readme を引く。**

各ファイルは**一つの呼び出しクラスだけ**を持つ。呼び出し側(claude)は、
そのクラスをインスタンス化して `run()` を呼ぶだけでよい
(CLI 引数のパースはしない。`if __name__ == "__main__"` も置かない)。

    from DEM.ai.claude_code.interface.world.list_places import ListPlaces
    ListPlaces(kind="村").run()

db の触り方(入口越し・読み取り・md との同期)は CLAUDE.md の「db への接続」「md と db の同期」を見る。

## 依頼内容 → 呼ぶコード

`DEM.ai.claude_code.interface.` を頭に付けて import する。

| 依頼内容(言い回しの例)           | 呼ぶコード                                                                 |
| ---------------------------------- | -------------------------------------------------------------------------- |
| 「同期して」「sync_db」             | `sync.import_db.ImportDb()` → `sync.export_db.ExportDb()`(= `sync_db`)。件数を辞書で返す。`ExportDb` は前回の同期より後に手で書かれた md があれば止まる(`ExportDb(force=True)` で押し切る) |
| 「どんな場所がある?」「村の一覧」   | `world.list_places.ListPlaces(kind=None)`                                    |
| 「この場所の近くには何がある?」     | `world.list_neighbors.ListNeighbors(place_id, kind=None, limit=None)`。同じ星の他の場所の方角・距離・高低差を近い順に返す |
| 「人物の一覧」「誰がいる?」         | `world.list_characters.ListCharacters()`                                     |
| 「人物同士の関係は?」               | `world.list_character_relations.ListCharacterRelations(character_id=None)`   |
| 「出来事の一覧」                     | `world.list_events.ListEvents()`(全件)。絞るなら `story.read_events.ReadEvents(time=…)` か、`ReadEvents(place_id=…)` / `ReadEvents(character_id=…)` / `ReadEvents(event_id=…)`(どの表の id かを名前で渡す) |
| 「このアイデアは何?」「アイデアを調べて」 | `world.search_ideas.SearchIdeas(keyword)`                              |
| 「場所を足して」                     | `randomizer.create_random_place.CreateRandomPlace()` で下書き → 内容を決めて `randomizer.commit_place.CommitPlace(place)` |
| 「人物を足して」                     | `randomizer.create_random_character.CreateRandomCharacter()` → `randomizer.commit_character.CommitCharacter(character)` |
| 「出来事を足して」                   | `randomizer.create_random_event.CreateRandomEvent()` → `randomizer.commit_event.CommitEvent(event)` |
| 「この人物の出自・居場所を足して」   | `randomizer.commit_character_place.CommitCharacterPlace(place)`              |
| 「この二人の相関を足して」           | `randomizer.commit_character_relation.CommitCharacterRelation(relation)`     |
| 「アイデアを足して」                 | `randomizer.commit_idea.CommitIdea(idea)`                                    |
| 「場所を直して」                     | `randomizer.update_place.UpdatePlace(place)`                                 |
| 「人物を直して」                     | `randomizer.update_character.UpdateCharacter(character)`。出自・居場所は `randomizer.update_character_place.UpdateCharacterPlace(place)`、相関は `randomizer.update_character_relation.UpdateCharacterRelation(relation)` |
| 「場所を消して」                     | `randomizer.delete_place.DeletePlace(place_id)`                              |
| 「アイデアを直して」                 | `randomizer.update_idea.UpdateIdea(idea)`。`id` 必須、渡した欄だけ直す       |
| 「アイデアを消して」                 | `randomizer.delete_idea.DeleteIdea(idea_id)`。下位のアイデアが残っていれば止まる |
| 「ミームを抜き出して」               | `meme.extract_memes.ExtractMemes()`。アイデア・oracle(`worlds/oracle/` の著者の覚え書き)・人物の筋書き(`# plot`)から抜き出し、`meme` テーブルへ足す。足した件数を返す |
| 「作品の一覧」                       | `story.list_stories.ListStories()`                                           |
| 「話を書き始める」「次の話を書く」   | `story.start_story.StartStory(story_id)`。同期確認・見出し・直前の話・断面・顔ぶれを一度に出す |
| 「前の話を読ませて」                 | `story.read_episodes.ReadEpisodes(story_id, count=10, before=None, text=True)` |
| 「その時点の顔ぶれは?」             | `story.read_cast.ReadCast(story_id, time=None)`                              |
| 「その場所・その時点の様子は?」     | `story.read_brief.ReadBrief(place_id, time)`                                 |
| 「この人物の周りで何が起きている?」 | `story.read_surroundings.ReadSurroundings(character_id, time)`               |
| 「この人物を本文用にそろえて」       | `story.read_character.ReadCharacter(character_id, time=None)`                |
| 「作品を作る」「筋書きを足して」     | `story.commit_story.CommitStory(story)`。筋書きは作品の `text` に書く        |
| 「作品を直して」「筋書きを直して」   | `story.update_story.UpdateStory(story)`                                      |
| 「作品を消して」                     | `story.delete_story.DeleteStory(story_id)`。話が残っていれば止まる           |
| 「本文を確定する」「話の種を入れる」 | `story.commit_episode.CommitEpisode(episode)`。`key`(種)か `text`(本文)のどちらかがあればよい |
| 「未同期の話は残ってる?」           | `story.list_unsynced_episodes.ListUnsyncedEpisodes(story_id=None)`           |
| 「世界観へ反映済みにする」           | `story.set_episode_synced.SetEpisodeSynced(story_id, number, synced=True)`   |
| 「世界を進めて」「ループを回して」   | 入口ではなく常駐ループ。「常駐ループ」を見る                                  |
| 「毎日のルーチン」「サブキャラの次の出来事を起こして」 | 入口ではなく常駐ループ側。「常駐ループ」の表の `daily_event` |

**まだ入口が無いもの**(頼まれたら作ってから行う): 出来事の修正・削除、人物の削除。

筋書き(`plot` / `character_plot`)のテーブルは無い。場所に掛かる筋書きは作品(`story`)の
`text` に、人物に掛かる筋書きはその人物の `text` の `# plot` の節に書く。

人物が持つミーム(行動原理の芯。`meme` テーブル)も専用の節は無く、その人物の `text` の
`# meme` 節に、持つミームの文面を箇条書きでそのまま書く。人物は複数のミームを持ってよい。
`meme` テーブル自体はアイデア(`idea`)・oracle・人物の筋書きから抜き出して貯めるだけで、
人物との FK は持たない(ミームは人物の間を移り変わり・伝染していくため)。

補足:

- 話(`episode`)の md だけは `# data` `# key` `# text` の三節を持つ。`# key` は作者が
  入れる種(AI 生成前)、`# text` は AI か作者が書く、投稿する本文。時期・場所・視点は
  `# data` の `start` / `end` / `place` / `viewpoint` に入る
- 本文は一話 5000〜8000 字(`DEM/ai/instructions/style.py` の `EPISODE_TARGET_LETTERS`)。
  場面の数と一場面の長さは決めず、中身に合わせる。**書く直前に種を場面まで割ってから本文に入る**。種はその話ぶんで 300〜500 字を目安に、
  `## 場面` の箇条書き(`場所 / 出る人 / そこで変わること`)と `## 狙い` で書く:

```
# key
## 場面

1. エンピレオ 面会室 / ミレア・カシル / カシルが原初型の中身を明かす
2. 住まい / ミレア / 追放と遺伝凍結処理の通達が届く
3. 住まい / ミレア・ノア / 四歳のノアの身体と白い灯りを見せる
4. 住まい 夜 / ミレア・アウレア・ピリム / 外装を出す。アウレアが頼みごとをする
5. 都の縁 → 地上 / ミレア・ノア・ピリム / 落ちる。ローザ諸都市同盟に着く

## 狙い

前日譚をここで閉じる。父の顔は最後まで見せない。
```
- `ExportDb` は md の写しに加えて、星ごとの地図 `{id}_map.svg`・`../worlds/maps/map.html`・
  人物相関の `../worlds/maps/relation.html` も描く。`ImportDb` は md → db の逆向き
- 場所の輪郭は `polygon` 欄(GeoJSON の Polygon。`[[経度, 緯度], ...]` の環を渡せば
  閉じて揃える)で `CommitPlace` / `UpdatePlace` から入れる。経緯度が無い面の場所
  (大陸など)にも持たせられ、地図では薄い面として描く

## 常駐ループ

世界の生成(出来事・人物・場所・本文)は主に `DEM/ai/local_ai/` の常駐ループが行う。
その起動だけは運用タスクとして直接呼んでよい。

| したいこと                                   | ローカル AI                                | Claude Code                                                        |
| -------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------ |
| 時間を進める                                 | `local_ai_time_keeper.loop_time()`         | `claude_code_time_keeper.claude_main()` / `story_writer.write_story()` |
| ある作品の開始から指定年数ぶん進める         | `local_ai_time_keeper.loop_time_for_story()` | `claude_code_time_keeper.claude_story_years_main()`               |
| サブキャラ一人の次の出来事を一件起こす(毎日のルーチン) | `local_ai_time_keeper.daily_event()`       | `claude_code_time_keeper.claude_daily_event_main()`                |

(`DEM.ai.local_ai.` / `DEM.ai.claude_code.` を頭に付ける)

毎日のルーチンは、人物ごとに生まれてから 5〜20 年後を起点に自分の時を刻む。作品の時期には合わせず、
作品の本文(筋書き)も渡さない。出来事の候補は、出来事の種(`event_seed` テーブル。md には出さない)から
ランダムに引いた種か、直前の出来事からの連想で立てる。種は作品の本文・話の種(`key`、無ければ本文)・
人物の `# plot` の節・出来事の本文から、時代・場所・固有名詞を抜いて抜き出したもの。ルーチンの頭で、
`event_seeded` が false の元だけから抜き出して true にする(`DEM/ai/time_keeper/event_seed.py`)。
抜き出しは元ごとに一度だけ。本文を書き直して抜き出し直したいときは、その md の `event_seeded` を false に戻す。
抜き出すときは似た種があるかを見ない。棚卸し前(`consolidated` が false)の種が 50 件たまったら、ルーチンの頭で
AI に棚卸し済みの種と見比べさせ、同じ出来事の言い換えだけをまとめる(`event_seed.consolidate`)。
人物ごとに時を刻むので、出来事を起こす時点より後に、別の人物の出来事が既にあることがある。その場所か当事者に掛かる
そうした出来事は、要約を添えて「この時点より後に既に決まっている出来事」として渡し、矛盾させない。

上の表の「作る」「確定する」入口を使えば、Claude も対話の中で人物・場所・出来事の
内容を決めて確定してよい。

## 作り方

置き場所は `<領域>/<動詞_対象>.py`。領域はいまのところ次の五つ。

- `randomizer/` — ランダム生成(作る／確定する)と、確定済みレコードの修正
- `story/` — 作品・話(`story`/`episode`)まわりの読み書き(材料を引く・本文を確定する)
- `sync/` — db と md の同期
- `world/` — 場所・人物・アイデア・出来事の一覧(読む専用)
- `meme/` — アイデア・oracle・人物の筋書きからのミームの抽出

- **「作る」と「確定する」を別ファイルに分ける。** 「作る」側(`create_random_*`)は
  db に一切触れず、素の辞書 / JSON を返すだけ。db を触るのは「確定する」側だけ
- 辞書 / JSON で受け渡しするのは、Bash 呼び出しをまたいでも(＝プロセスが
  切り替わっても)中身を運べるようにするため。SQLAlchemy のオブジェクトや
  session を返すと、次の呼び出しでは中身が失われる
- 実在レコードを指す欄(id)は、確定する側が呼び出し時に db に居るか確かめる
  (`check_exists`)。スキーマに無い欄が混ざっていたらそこで止める(`check_columns`)

各領域に共通する処理はクラスへ寄せ、その領域の入口の**上位**(`<領域>/_base.py`)
に置く。さらに四領域をまたいで共通する部分(db セッションを開いて渡す・
「確定する」系の実在確認とスキーマ列チェック等)は、一段上の
`DEM/ai/claude_code/interface/_base.py` に置く。`_rows.py` と同じく、先頭が `_` の
ファイルはそれ自体が claude の呼ぶ入口ではない。

```
Entrypoint(interface/_base.py)
├─ SessionEntrypoint            db セッションを開いて execute(session) へ渡す
│   ├─ CommitEntrypoint         「確定する」系の共通処理(parse/check_columns/check_exists)
│   │   ├─ randomizer.CommitDraft   → commit_*.py / update_*.py / delete_place.py
│   │   └─ story.StoryCommit        → commit_*.py / update_story.py / delete_story.py / set_episode_synced.py
│   ├─ world.WorldQuery          → list_*.py / search_ideas.py
│   └─ story.StoryQuery          → list_*.py / read_*.py / start_story.py
└─ randomizer.RandomDraft        db に触れない下書き作成 → create_random_*.py
```

(`sync/` の二つと `meme.extract_memes.ExtractMemes` は、`execute(session)` の外で
db セッションを開き直したいので `Entrypoint` を直接継ぐ)

## 引き方は query 側にある

読む側の中身は `DEM/data_access_logic/query/` にある。

| モジュール                     | 何のため                                                     |
| ------------------------------ | ------------------------------------------------------------ |
| `common_query.py`              | 時刻の扱い・断面・顔ぶれ・場所の道筋                         |
| `character_simulation_query.py` | 人物を軸に周辺を読む(`read_surroundings`)                   |
| `dictionary_query.py`          | アイデア(辞書)のキーワード検索                               |
| `story_createion_query.py`     | 場所に掛かる作品(`story`)の読み出し                          |
| `world_createion_query.py`     | 生きている人物、広さの整合、進行中の判定               |
| `event_seed_query.py`          | 出来事の種をまだ抜き出していない元(`event_seeded` が false) |

ここのファイルはその薄い呼び出し面で、**SQL は組み立てない。**
引く条件は時刻とレコードの id だけで表す。足りない引き方が出てきたら
query 側に関数を足して、ここに入口を一つ被せる。
