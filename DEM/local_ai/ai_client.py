#!/usr/bin/env python3
"""ローカル AI(Ollama)を叩く、環境非依存の薄いクライアント。db には触れない。

環境変数: `DEM_LOCAL_AI_HOST`(Ollama のベース URL、既定 `http://localhost:11434`)、
`DEM_LOCAL_AI_MODEL`(モデル名、必須)。
`DEM_AI_BACKEND` を `claude` にすると、生成だけ `DEM/claude_ai/ai_client.py`
(Claude Code)へ回す。呼び出し側(`time_keeper/` の各生成器)は変えない。
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

# CWD 次第では `.env` を見つけられない(python-dotenv は既定でカレント
# ディレクトリから探す)ため、このファイルの位置からリポジトリルートを
# 特定して明示的に渡す。
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class LocalAIError(RuntimeError):
    """ローカルAIサーバとの通信・応答が失敗したときに投げる。"""


_DEFAULT_OPTIONS = {
    "temperature": 0.6,
    "repeat_penalty": 1.3,
    "num_ctx": 16384,
}


def _backend() -> str:
    return os.environ.get("DEM_AI_BACKEND", "local")


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
    format: dict | str | None = None,
    timeout: float = 120.0,
    options: dict | None = None,
) -> str:
    """Ollamaの `/api/generate` を叩き、生成テキストを返す。

    `options` は Ollama の `options`(temperature 等)に上書きでマージする。
    省略時は `_DEFAULT_OPTIONS` を使う。`format` は Ollama にそのまま渡す
    (JSON Schema の辞書、または `"json"`)。
    """
    if _backend() == "claude":
        from DEM.claude_ai import ai_client as claude_ai_client
        try:
            return claude_ai_client.generate(
                prompt, system=system, format=format, timeout=timeout, options=options)
        except claude_ai_client.ClaudeAIError as error:
            raise LocalAIError(str(error)) from error

    payload: dict = {
        "model": _model(),
        "prompt": prompt,
        "stream": False,
        "options": {**_DEFAULT_OPTIONS, **(options or {})},
    }
    if system is not None:
        payload["system"] = system
    if format is not None:
        payload["format"] = format
        payload["think"] = False

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
    schema: dict,
    *,
    system: str | None = None,
    timeout: float = 120.0,
    options: dict | None = None,
) -> dict:
    """`generate` を `schema`(JSON Schema)で構造化出力に制約して呼び、パースした辞書を返す。"""
    text = generate(
        prompt, system=system, format=schema, timeout=timeout, options=options)
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise LocalAIError(
            f"ローカルAIサーバの応答がJSONとしてパースできない: {text!r}") from error


def try_generate_json(
    prompt: str,
    schema: dict,
    *,
    system: str | None = None,
    timeout: float = 120.0,
    options: dict | None = None,
) -> dict:
    """`generate_json` を試し、失敗(接続不可・応答がJSONとして壊れている)なら空の辞書を返す。"""
    try:
        return generate_json(prompt, schema, system=system, timeout=timeout, options=options)
    except LocalAIError as error:
        print(f"[ai_client] ローカルAIの応答が使えなかったため既定値で進める: {error}")
        return {}
