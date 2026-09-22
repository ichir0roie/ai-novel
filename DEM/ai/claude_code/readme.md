# claude_code

`DEM/ai/local_ai/`(Ollama)と**同じ仕様**で、生成を Claude Code(`claude -p`)にやらせる側。
常駐ループの本体(生成器・時刻・定数)は上位の `DEM/ai/time_keeper/` にあり、local_ai と
claude_code はそこへ自分の `ai_client` を渡すだけの薄い入口になっている。

```
DEM/ai/time_keeper/          常駐ループの本体(両方で共用)。生成器は AI を `ai` 引数(`_ai.AIClient`)で受け取る
DEM/ai/claude_code/
  ai_client.py            `DEM/ai/local_ai/ai_client.py` と同じ関数(generate / generate_json / try_generate_json)。
                          中身は `claude -p --output-format json --json-schema …` の subprocess
  claude_code_time_keeper.py  `DEM/ai/time_keeper/main.py` に claude_code の ai_client を渡して回す入口
  story_writer.py         作品の次の話を書いて db へ確定する(local_ai に無い、ここだけの生成器)
  interface/              Claude が db を読み書きする入口(一覧は interface/readme.md)
```

## 仕組み

- 各呼び出しは `--tools ""`(道具なし)・`--no-session-persistence`・`--system-prompt`
  で、単発の「プロンプト → JSON」に絞る。カレントは一時ディレクトリにして、
  このリポジトリの `CLAUDE.md` や設定を読み込ませない
- 認証は CLI に任せる(`claude login` 済みか `ANTHROPIC_API_KEY`)
- ループの終わりに Claude Code の呼び出し回数・トークン・費用を出す

## 環境変数(`.env` でよい)

| 変数                    | 意味                                                        |
| ----------------------- | ----------------------------------------------------------- |
| `DEM_CLAUDE_AI_COMMAND` | 実行する CLI。既定 `claude`                                  |
| `DEM_CLAUDE_AI_MODEL`   | `--model` に渡す。既定 `claude-sonnet-5`                     |
| `DEM_CLAUDE_AI_EFFORT`  | `--effort` に渡す(low / medium / high)。既定 `low`          |
| `DEM_CLAUDE_AI_TIMEOUT` | 一回の呼び出しを待つ秒数の下限。既定 300(CLI の起動ぶん、Ollama 向けの 120 秒では足りないことがある) |

## 使い方

常駐ループ(local_ai と同じ引数):

```
PYTHONUTF8=1 .venv/Scripts/python.exe -c "
from DEM.ai.claude_code.claude_code_time_keeper import claude_main
claude_main(year=2027, max_days=30)
"
```

`year` を省くと db の最新の時刻から続ける。プロット(`Plot`)が一件も掛かって
いない時刻に来たら止まるのも local_ai と同じ。

本文を書く(作品 `story_id` の次の話を 1 話。`episodes_to_write` で続けて書く):

```
PYTHONUTF8=1 .venv/Scripts/python.exe -c "
from DEM.ai.claude_code.story_writer import write_story
write_story(story_id=1, episodes_to_write=1)
"
```

材料は `start_story` 入口と同じ(作品の見出し・直前の話・断面・顔ぶれ)。
未同期の話が残っている作品は書かない。書いた話は `synced=True` で確定する。
本文の書き方は `DEM/ai/instructions/story_writing.py` にある。
