#!/usr/bin/env python3
"""ローカル AI(Ollama)を叩く、環境非依存の薄いクライアント。db には触れない。

環境変数: `DEM_LOCAL_AI_HOST`(Ollama のベース URL、既定 `http://localhost:11434`)、
`DEM_LOCAL_AI_MODEL`(モデル名、必須)。
"""
from __future__ import annotations

import json
import os
import urllib.request


class LocalAIError(RuntimeError):
    """ローカルAIサーバとの通信・応答が失敗したときに投げる。"""


# Ollama の既定値(temperature 0.8 / repeat_penalty 1.1 前後)のまま使うと、
# 小型モデル(ノート PC の gemma3n:e2b/e4b、GPU PC の gemma4:12b-it-qat 共通)は、
# 渡した設定が薄い場面で高確率トークン(場所を問わず使い回せる抽象的なムード語)
# へ収束しやすい。temperature を少し下げ、repeat_penalty を上げることで、
# 同じ言い回しの多用を抑える。gemma4 系は「寡黙に」のような指示があっても
# 会話が続くほど応答が長くなる傾向が報告されているため、この効果は引き続き要る。
#
# num_ctx は明示しないと Ollama の既定(2048〜4096 程度)に落ちる。gemma4 は
# 数万〜数十万トークンの context window を持つモデルだが、Ollama はモデルの
# 対応幅に関係なく既定値で黙って古い方から切り詰める(エラーは出ない)。
# event_progression_generator._progress_place の1呼び出しだけでも、人物・個体
# 最大20件ずつ+text+plot を渡すため、既定のままでは日本語で簡単に既定値を
# 超えて古い情報から見えなくなる。VRAM(3080 10〜12GB, Q4量子化)に収まる
# 範囲で余裕を持たせておく。
_DEFAULT_OPTIONS = {
    "temperature": 0.6,
    "repeat_penalty": 1.3,
    "num_ctx": 16384,
}

# 呼び出し側の options で明示的に think を渡さないこと。gemma4 は
# /api/generate では think を渡さない限り既定で思考(reasoning)を出力しないが、
# think: false を明示すると format(JSON制約)が黙って無視される既知の不具合が
# Ollama 側にある(2026年時点)。JSON モードで使う本クライアントでは、
# think キー自体を options に含めないのが最も安全。


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
    """`generate_json` を試し、失敗(接続不可・応答がJSONとして壊れている)なら空の辞書を返す。"""
    try:
        return generate_json(prompt, system=system, timeout=timeout, options=options)
    except LocalAIError as error:
        print(f"[ai_client] ローカルAIの応答が使えなかったため既定値で進める: {error}")
        return {}
