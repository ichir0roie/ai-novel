# ai_instructions

**ローカル AI へのプロンプトに埋め込む基準を、定数として置く場所。**

`DEM/local_ai/` の常駐ループ・量産系は、Claude を介さず db への確定まで
自動で回る。対話越しに `IHG/*.md` を読めないので、そこで守らせたい基準は
ここに定数として切り出し、各生成のシステムプロンプトへ文字列として渡す。

**ここは db にも AI クライアントにも触れない。定数を持つだけ。**

## 正本がどちらにあるか

ファイルごとにどちらが正本か、なぜそういう分担にしているかは
`IHG/README.md`「常駐ループへ渡す基準」にまとめてある。**ここでは繰り返さない。**
直すときは、まず `IHG/README.md` の表でどちらを直すべきかを確かめる。

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

定数を書くときの注意(避けたい語を具体例として書かない、等)も
`IHG/README.md`「常駐ループへ渡す基準」にまとめてある。
