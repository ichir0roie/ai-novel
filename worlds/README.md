# worlds

世界観ごとの設定を置く。1 つの世界観を複数の作品で使い回せる。

```
worlds/<world-id>/
  world.md          中核設定（core/templates/world-template.md から）
  glossary.md       固有名詞・用語の一覧。表記ゆれ防止
  characters/       登場人物（core/templates/character-template.md から）
  objects/          アイテム・組織・地名などの個別設定
```

## 原則

- **物語に必要な分だけ作る。** 使われない設定は書かないほうがいい
- **制限を書く。** 能力には必ず代償か制限を設ける。制限のない設定は物語を殺す
- **本文で生まれた設定は必ずここへ書き戻す。** 本文にしかない設定は次の話で矛盾する
- **固有名詞は `glossary.md` に登録する。** 表記ゆれの大半はここで防げる

## world-id の付け方

半角英数とハイフン。作中の呼び名と違ってよい（`lunar-empire`, `neo-akihabara`）。
