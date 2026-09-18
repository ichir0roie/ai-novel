# records / 地球系

**台帳。** 文章で書いた設定を、いつ・どこで・誰が・いくつ、の形に起こしたもの。
読み方と使いどころは `core/chronicle.md`。

```
config.json   星と、光の遅れと、物語の現在
場所.md       地理。親をたどって内側・外側を決める
人物.md       行動の主語になれるもの（個人・組織・国・集団・仕組み）
出来事.md     起きたこと
行動.md       主語のある出来事。動機・代償・結果つき
指標.md       数で追えるもの
関係.md       誰と誰が、どういう間柄か
火種.md       張っているもの。話はここから生える
```

## 守ること

- **文章が正、台帳が従。** 食い違ったら `worlds/地球系/**/*.md` を先に直す
- **出典のない行を足さない。** どの設定ファイルから来たかを必ず書く
- **上書きしない、追記する。** 状態が変わったら新しい年の行を足す
- **設定にない数は乱数で振る。** `tools/roll.py`。引いた目は `../rolls.md` へ
- セル内の `|` は `\|`。改行は使えない（`<br>` で代用）

## よく使う

```
python3 tools/chronicle.py brief --star 入植星 --year 4360 --place mushvan-land
python3 tools/chronicle.py check
python3 tools/chronicle.py add --table event --set 年=4361 ...
```

`chronicle.db` は組み上げた結果なので git に入れない。消しても `build` で戻る。
