#!/usr/bin/env python3
"""
ローカルAI(Ollama)を叩く、環境非依存の薄いクライアント。

<https://huggingface.co/google/gemma-4-E2B>

`oracle/system-idea/ローカル環境AI.md` の設計に沿う: notePC(テスト、
`gemma4:e2b` 想定)とGPU PC(本番、`gemma4:12b` 想定)で呼び出し処理は
共通にし、差分はホスト／モデル名の環境変数だけに閉じる。

- `DEM_LOCAL_AI_HOST`: OllamaのベースURL(既定 `http://localhost:11434`)

db には一切触れない。返すのは生成テキスト(`generate`)／パース済み辞書
(`generate_json`)だけで、`DEM/randomizer/` の「作る」側と同じく、db への
書き込みは呼び出し側(`DEM/claude_interface/` の「確定する」入口)の仕事。

<https://huggingface.co/google/gemma-4-E2B>
sudo curl -fsSL https://ollama.com/install.sh | sh



"""
from __future__ import annotations

import json
import os
import urllib.request


class LocalAIError(RuntimeError):
    """ローカルAIサーバとの通信・応答が失敗したときに投げる。"""


# Ollama の既定値(temperature 0.8 / repeat_penalty 1.1 前後)のまま使うと、
# gemma3n:e2b/e4b のような小型モデルは、渡した設定が薄い場面で高確率トークン
# (場所を問わず使い回せる抽象的なムード語)へ収束しやすい。temperature を
# 少し下げ、repeat_penalty を上げることで、同じ言い回しの多用を抑える。
_DEFAULT_OPTIONS = {
    "temperature": 0.6,
    "repeat_penalty": 1.3,
}


def _host() -> str:
    return os.environ.get("DEM_LOCAL_AI_HOST", "http://localhost:11434")


def _model() -> str:
    model = os.environ.get("DEM_LOCAL_AI_MODEL")
    if not model:
        raise LocalAIError("環境変数 DEM_LOCAL_AI_MODEL が設定されていない")
    return model


def generate(
    prompt: str,
    *,
    system: str | None = None,
    json_mode: bool = False,
    timeout: float = 120.0,
    options: dict | None = None,
) -> str:
    """Ollamaの `/api/generate` を叩き、生成テキストを返す。

    `options` は Ollama の `options`(temperature 等)に上書きでマージする。
    省略時は `_DEFAULT_OPTIONS` を使う。
    """
    payload: dict = {
        "model": _model(),
        "prompt": prompt,
        "stream": False,
        "options": {**_DEFAULT_OPTIONS, **(options or {})},
    }
    if system is not None:
        payload["system"] = system
    if json_mode:
        payload["format"] = "json"

    url = f"{_host().rstrip('/')}/api/generate"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read())
    except OSError as error:
        # `urllib.error.URLError` は `OSError` のサブクラスだが、読み取り中の
        # タイムアウトは(接続時と違い)素の `TimeoutError` のまま urlopen を
        # 抜けてくることがある。まとめて `OSError` で受けて、常駐ループ
        # (`try_generate_json`)がどちらも同じ `LocalAIError` として拾えるようにする。
        raise LocalAIError(f"ローカルAIサーバ({url})に接続できない: {error}") from error

    text = result.get("response")
    if text is None:
        raise LocalAIError(f"ローカルAIサーバの応答に 'response' が無い: {result}")
    return text


def generate_json(
    prompt: str,
    *,
    system: str | None = None,
    timeout: float = 120.0,
    options: dict | None = None,
) -> dict:
    """`generate` をJSONモードで呼び、パースした辞書を返す。"""
    text = generate(
        prompt, system=system, json_mode=True, timeout=timeout, options=options)
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise LocalAIError(
            f"ローカルAIサーバの応答がJSONとしてパースできない: {text!r}") from error


def try_generate_json(
    prompt: str,
    *,
    system: str | None = None,
    timeout: float = 120.0,
    options: dict | None = None,
) -> dict:
    """`generate_json` を試し、失敗(接続不可・応答がJSONとして壊れている)なら
    空の辞書を返す。

    `DEM/local_ai/time_keepr/` の常駐ループは claude を介さず回り続ける前提
    なので、一件の応答が壊れていたというだけでループ全体を止めない。呼び出し
    側は返る辞書に対して `.get(key) or 既定値` の形で使う想定(空辞書なら
    その件はすべて既定値で進む)。
    """
    try:
        return generate_json(prompt, system=system, timeout=timeout, options=options)
    except LocalAIError as error:
        print(f"[ai_client] ローカルAIの応答が使えなかったため既定値で進める: {error}")
        return {}
