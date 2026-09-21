# ai_instructions

**ローカル AI へのプロンプトに埋め込む基準を、定数として置く場所。**

`DEM/local_ai/` の常駐ループ・量産系は、Claude を介さず db への確定まで
自動で回る。対話越しに `IHG/*.md` を読めないので、そこで守らせたい基準は
ここに定数として切り出し、各生成のシステムプロンプトへ文字列として渡す。

**ここは db にも AI クライアントにも触れない。定数を持つだけ。**

## 正本がどちらにあるか

**ファイルごとに、正本を一つに決めてある**(二重メンテを避けるため)。

| ファイル           | 正本                       | 中身                                   |
| ------------------ | -------------------------- | -------------------------------------- |
| `naming.py`        | `IHG/naming.md`            | 名づけの基準。定数はその**簡略版**     |
| `principles.py`    | `IHG/principles.md`「避けるもの」 | なろう系テンプレ回避。定数は**簡略版** |
| `event_writing.py` | **このファイル自身**       | 出来事の書き方・進め方。`IHG/chronicle.md` は理由だけを持つ |

- **簡略版のほう**(`naming.py` `principles.py`): Claude 自身が判断するときは
  定数ではなく `IHG/*.md` を直接読む。IHG 側を直したら、ここも合わせて直す
- **文面が正本のほう**(`event_writing.py`): Claude が `CommitEvent` を書くときも
  この定数の文面をそのまま基準にする。ルールの文面を変えたいときはここを直し、
  `IHG/chronicle.md` 側は理由(なぜその形にしたか)だけを見直す

## 誰が何を使っているか

| 定数                                                                            | 使う側                                                          |
| ------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `naming.TERM_NAMING_INSTRUCTION`                                                | `time_keeper/random_object_generator.py`(国・組織などの名)と、下の二つの土台 |
| `naming.PLACE_NAMING_INSTRUCTION`                                               | `time_keeper/random_location_generator.py`、`time_keeper/event_progression_generator.py`(新しい場所が生まれたとき) |
| `naming.CHARACTER_NAMING_INSTRUCTION`                                           | `time_keeper/random_character_generator.py`                     |
| `principles.AVOID_NARO_TEMPLATE_INSTRUCTION`                                    | `time_keeper/event_progression_generator.py`、`time_keeper/random_object_generator.py`、`random_drive_generator.py` |
| `event_writing.EVENT_RECORD_INSTRUCTION`                                        | `time_keeper/event_progression_generator.py`、`time_keeper/character_lifespan.py` |
| `event_writing.EVENT_RELATION_INSTRUCTION` `OBJECT_ACTION_INSTRUCTION`          | `time_keeper/event_progression_generator.py`                    |
| `event_writing.EVENT_PROGRESSION_INSTRUCTION` `EVENT_DURATION_INSTRUCTION`      | 同上                                                            |
| `event_writing.CHARACTER_TEXT_UPDATE_INSTRUCTION` `OBJECT_TEXT_UPDATE_INSTRUCTION` | 同上                                                          |
| `event_writing.RECENT_EVENT_LIMIT` `CHARACTER_NOTE_LIMIT` `CHARACTER_NOTE_SEPARATOR` | 同上(件数の上限。プロンプトではなく処理側で使う)           |

## 書き方

- **避けたい語を具体例として書かない。** 小型モデルほど、否定命令より例示
  された語のほうが強く残り、かえってその語を呼び出しやすくなる。避けたい
  傾向は「何を使うか」という**肯定形**で書く(`IHG/chronicle.md`「出来事の
  text は記録として書く」に経緯がある)
- 形式の指定(「小説として書かない」「セリフを書かない」)はこれに当たらない。
  語の例示ではないため
