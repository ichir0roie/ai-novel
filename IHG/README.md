# IHG

共通の作業方針とテクニックを書き留める場所。特定の作品に依存しない知見だけを置く。

| ファイル           | 内容                                       |
| ------------------ | ------------------------------------------ |
| `principles.md`    | **プロジェクトの目的と禁止事項。最優先**   |
| `workflow.md`      | **進め方。Claude はもう本文・出来事・人物などを直接生成しない** |
| `chronicle.md`     | **記録の取り方と、話を尽きさせない仕組み** |
| `naming.md`        | **用語と名づけの基準。日本語として自然に** |
| `ai_instructions/` | 常駐ループへ渡す基準の Python 定数(下の節)。**いま生成に実際に使われているのはここだけ** |

## IHG と DEM の分担

記録の**形**と**触り方**は IHG ではなく `DEM/` が決めている。

| 何を                       | どこが決めるか                               |
| -------------------------- | -------------------------------------------- |
| レコードの欄               | `DEM/db/schema.py`(+ `DEM/db/alembic/`)      |
| 読み書きの入口             | `DEM/claude_interface/`(一覧は `DEM/claude_interface/readme.md`) |
| 引き方(Select の組み立て)  | `DEM/data_access_logic/query/`               |
| 自動で世界を進める常駐ループ | `DEM/local_ai/`                              |

**IHG はその使い方と判断の基準を書くところで、欄を増やす場所ではない。**

## 常駐ループへ渡す基準(IHG/ai_instructions/)

**世界の生成はもう `DEM/local_ai/` の常駐ループ(`time_keeper/` 配下など)
だけが行う。** Claude が対話の中で `IHG/*.md` を読んで名づけ・出来事の
判断を直接下す、という経路はもう無い(`IHG/workflow.md`)。だから、常駐
ループが使う基準は `IHG/ai_instructions/` に Python の定数として切り出し、
各生成のシステムプロンプトへ文字列として埋め込む(**db にも AI クライアント
にも触れない。定数を持つだけ**)。**正本(どちらを直せば反映されるか)は、
ファイルごとに一つに決めてある**(二重メンテを避けるため)。

| 定数ファイル        | 正本                                                              |
| ------------------- | ------------------------------------------------------------------ |
| `naming.py`         | `naming.md`(定数はその**簡略版**)                                 |
| `principles.py`     | `principles.md`「避けるもの」(定数は**簡略版**)                    |
| `event_writing.py`  | **定数の文面そのものが正本**(`chronicle.md` は理由だけを持つ)     |

- **簡略版のほう**(`naming.py` `principles.py`): `naming.md` は
  乱数で言語を一つ引いてから固有名詞を組み立てる、といった対話越しの手順を
  前提にしていて、そのままでは JSON 生成 1 回で名づけを終える常駐ループに
  埋め込めない。定数はその要旨だけを持つ簡略版でしかない。**`naming.md`
  `principles.md` はもう Claude が対話の中で踏む手順ではなく、なぜ定数を
  その形にしたかの設計根拠(正本)として残している。** 名づけ・なろう系回避の
  基準を変えたくなったら、まず `naming.md` `principles.md` を直し、
  そのうえで対応する定数を揃えて直す
- **文面が正本のほう**(`event_writing.py`): 出来事の書き方は対話越しの手順を
  要らない(手順ではなく文面そのものが基準)ので、定数の文面をそのまま正本に
  できる。`event_progression_generator.py` `character_lifespan.py` が出来事を
  生成するときも、この定数の文面をそのまま基準にする。ルールの文面を
  変えたいときは `event_writing.py` を直し、`chronicle.md` 側は理由
  (なぜその形にしたか)だけを見直す

**定数を書くときの注意**: 避けたい語を具体例として書かない。小型モデルほど、
否定命令より例示された語のほうが強く残り、かえってその語を呼び出しやすく
なる。避けたい傾向は「何を使うか」という**肯定形**で書く
(`chronicle.md`「出来事の text は記録として書く」に経緯がある)。形式の指定
(「小説として書かない」「セリフを書かない」)はこれに当たらない。
**近い内容の定数を複数持ちたくなったら、文面を二重に書かず、差分だけを
引数に取る関数から組み立てる**(`event_writing.py` の
`CHARACTER_TEXT_UPDATE_INSTRUCTION` / `OBJECT_TEXT_UPDATE_INSTRUCTION` が実例)。

### どの生成器が何を使っているか

| 定数                                                                                 | 使う側                                                                       |
| ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `naming.TERM_NAMING_INSTRUCTION`                                                       | `time_keeper/random_object_generator.py`(国・組織などの名)と、下の二つの土台 |
| `naming.PLACE_NAMING_INSTRUCTION`                                                      | `time_keeper/random_location_generator.py`、`time_keeper/event_progression_generator.py`(新しい場所が生まれたとき) |
| `naming.CHARACTER_NAMING_INSTRUCTION`                                                  | `time_keeper/random_character_generator.py`                                   |
| `principles.AVOID_NARO_TEMPLATE_INSTRUCTION`                                           | `time_keeper/event_progression_generator.py`、`time_keeper/random_object_generator.py` |
| `event_writing.EVENT_RECORD_INSTRUCTION`                                               | `time_keeper/event_progression_generator.py`、`time_keeper/character_lifespan.py` |
| `event_writing.EVENT_RELATION_INSTRUCTION` `OBJECT_ACTION_INSTRUCTION`                 | `time_keeper/event_progression_generator.py`                                  |
| `event_writing.EVENT_PROGRESSION_INSTRUCTION` `EVENT_DURATION_INSTRUCTION`             | 同上                                                                          |
| `event_writing.CHARACTER_TEXT_UPDATE_INSTRUCTION` `OBJECT_TEXT_UPDATE_INSTRUCTION`     | 同上                                                                          |
| `event_writing.RECENT_EVENT_LIMIT` `CHARACTER_NOTE_LIMIT` `CHARACTER_NOTE_SEPARATOR`   | 同上(件数の上限。プロンプトではなく処理側で使う)                             |

(呼び出し元はすべて `DEM/local_ai/`。`IHG/ai_instructions/` 自体は db にも
`DEM/` の他のどこにも依存しない、定数だけの葉のパッケージ)

## 更新のしかた

書いていて「次からはこうしよう」と思ったことは、その場でここに追記する。
**指示を実行するだけで、文書を古いまま放置しない。**
直そうとして、既存の手順と矛盾する・情報が足りないと分かったら、
その場で作者に相談する。

作品固有の判断は作品(`story`)のレコードへ、
世界固有の判断はその世界線の場所のレコードへ書く。

うまくいかなかった書き方も残す価値がある。禁じ手として書いておくと同じ失敗を繰り返さない。
