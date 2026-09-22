
claudeにランダム生成とイベント生成をさせると、トークンがいくらあっても足りない。
ローカルPCやGPUを使用してオブジェクトを生成、経過させていく仕組みが必要。

## 構成案(2026-09-19 検討)

### 役割分担
- **claude(今のセッション)**: 本文執筆・設定の一貫性チェックなど、品質が要る部分に絞る
- **ローカルモデル**: イベント生成・ランダム生成の下書き(`DEM/randomizer/` が返す辞書の中身)を大量に作る側。
  `create_random_event` / `create_random_character` のような「作る」入口を、
  ローカルモデル呼び出しに差し替える or 前段に挟む形が既存の入口設計とも噛み合う
  (「作る」側は db に触れないので、ローカルで動かしても安全)

### 開発環境を2つに分ける
- **ノートPC(GPUなし)**: テスト環境。動作確認・実装のデバッグに使う。CPU推論できる軽量モデルを使う
- **GPU PC(RTX 3080、VRAM 10GB、12GB版なら12GB)**: 本番環境。大きめのモデルで実際の生成品質を出す
- **呼び出し側の処理(プロンプト組み立て・JSON整形・エラーハンドリング等)は両環境で共通にする。差分はモデル名/エンドポイントの切り替えだけに閉じる**(環境変数か設定ファイルで持たせ、コード分岐を作らない)

### モデル
両環境とも **Gemma系**([collection](https://huggingface.co/collections/google/gemma-4))に統一し、環境ごとにサイズだけ変える。

- **GPU PC(本番)**: [`gemma-4-12B-it`](https://huggingface.co/google/gemma-4-12B-it)。dense版・instruction-tuned。4bit量子化で10〜12GB VRAMに収まる規模感。**QAT(量子化を見込んで学習した)版が `Q4_K_M` と同等〜それ以上の品質のままメモリを切り詰められると報告されているため、Ollamaで動かすなら QAT 版を優先する**(下の「実際のタグ名」)
- **ノートPC(テスト)**: `gemma4:e2b`(it版)。on-device向けに設計されたモデルで、実効パラメータ2.3B(埋め込み込みで5.1B、Per-Layer Embeddingsでメモリを切り詰めている)。llama.cpp/LM Studio/Jan/Ollama向けの量子化版が多数出ておりCPUでも動く。生成品質の検証ではなく、呼び出し処理そのもの(プロンプト・JSON整形・入口への受け渡し)が動くかの確認に使う
- 出力は自由文ではなく **JSON スキーマに沿わせる**(`DEM/db/schema.py` の欄に合わせたプロンプト)。ダメならグラマー制約(後述の llama.cpp の GBNF)で型レベルに強制する
- **num_ctx を明示する。** Ollama は既定で 2048〜4096 程度に context window を切り詰める。gemma4 系は数万〜数十万トークンに対応するモデルだが、Ollama 側は対応幅を見ずに黙って古い方から切り詰めるため、既定のままだと渡した人物・個体一覧の一部が見えないまま生成されうる(`DEM/ai/local_ai/ai_client.py` の `_DEFAULT_OPTIONS` で対処済み)

### 実行環境
- **まずはこれで**: [Ollama](https://ollama.com/) — `ollama pull gemma4:12b-it-qat`(GPU PC)/ `ollama pull gemma4:e2b`(ノートPC)だけでモデルが降ってきて即HTTP API化される。どちらの環境でもOllamaのHTTP APIを同じインターフェースで叩けるので、呼び出し側コードを共通化しやすい
- **JSON出力を型で強制したい/VRAMをもっと切り詰めたい場合**: [llama.cpp](https://github.com/ggml-org/llama.cpp)(GGUF + GBNF文法)。Ollama内部もllama.cppベースなので、こだわりが出てきたら移行先として自然
- **vLLM** はマルチGPUや高スループットのサーバ用途向けで、3080一枚・個人PCの規模ではオーバースペック。将来GPUを増設するまでは検討しなくてよい

### 想定する呼び出しフロー
1. ローカルサーバ(Ollama等)にプロンプト(世界観の断面・既存レコードの抜粋など)を渡し、JSON下書きを生成させる。呼び出し先のモデル名/エンドポイントは環境変数等で外出しし、ノートPC/GPU PCで同じコードパスを通す
2. 返ってきたJSONを **そのまま db に書かない**。既存の設計通り、`DEM/ai/claude_code/interface/randomizer/` の「作る」側の戻り値と同じ形に整形するだけに留める
3. claude(このセッション)が中身を軽くレビューし、必要なら `commit_event` / `commit_character` のような「確定する」入口を呼んでdbへ反映する

### 無料サービス(GPUなし/補助用)
- ローカルGPUを用意する前の暫定・または動作確認用に、無料枠のあるホスト型API(例: OpenRouterの無料モデル、Google AI StudioのGemini無料枠)を一時的に使う手もある。ただし継続運用は「ローカルGPU + Ollama/vLLM」に寄せる方が、トークン制約からの解放という当初の目的に合う

### 未決事項
- ローカルモデルの出力品質をどう検収するか(claudeが逐次チェックする/サンプリングで抜き取りチェックする等)は運用しながら決める
- 3080は10GB/12GB版があるので、実機がどちらかで量子化レベル(下記QAT版のまま使うか、より軽い版に落とすか)を調整する

### Ollamaでの実際のタグ名(2026-09-21 確認)
- GPU PC(本番)は **`gemma4:12b-it-qat`**(QATの4bit版)。`Q4_K_M` 相当と同等〜それ以上の品質を保ったまま低VRAMで動くと報告されているため、素の `gemma4:12b` より優先する。プレーン版のタグは `gemma4:12b`
- ノートPC(テスト)は **`gemma4:e2b`**(QAT版は `gemma4:e2b-it-qat`)。Gemma 4 リリース前に本ドキュメントへ書いていた「`gemma3n:e2b` として配布」は誤り(Gemma 4 リリース前で存在しなかった旧世代 `gemma3n` を仮に使っていた記録)。**Gemma 4 は `gemma3n` とは別の `gemma4` ライブラリ名で配布されている**(`gemma4:e2b` `gemma4:e4b` `gemma4:12b` `gemma4:26b-a4b` 等)
- `DEM_LOCAL_AI_MODEL` は環境ごとの `.env`(gitignore対象)で切り替える。本ドキュメント更新時点でこのマシンの `.env` はまだテスト用の `gemma3n:e2b` のまま(ノートPC想定の暫定値)。`gemma4:e2b` / `gemma4:12b-it-qat` へ切り替えるのは、そのモデルを実際に `ollama pull` してから

