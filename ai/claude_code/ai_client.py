#!/usr/bin/env python3
"""Claude Code(`claude -p`)を叩く、`ai/local_ai/ai_client.py` と同じ顔の薄いクライアント。db には触れない。

環境変数: `DEM_CLAUDE_AI_COMMAND`(実行する CLI、既定 `claude`)、
`DEM_CLAUDE_AI_MODEL`(モデル名、既定 `claude-sonnet-5`)、
`DEM_CLAUDE_AI_EFFORT`(low / medium / high、既定 `low`)、
`DEM_CLAUDE_AI_TIMEOUT`(一回の呼び出しを待つ秒数の下限、既定 300。呼び出し側の
`timeout` が Ollama 向けに短くても、この値までは待つ)。
認証は CLI 側(`claude login` 済みか `ANTHROPIC_API_KEY`)に任せる。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class ClaudeAIError(RuntimeError):
    """Claude Code の起動・応答が失敗したときに投げる。"""


# 呼んだ回数とトークン・費用の積算。`usage_summary` でループの終わりに出す。
_tally = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


_DEFAULT_MODEL = "claude-opus-5-5"
_DEFAULT_EFFORT = "medium"


def _command() -> str:
    name = os.environ.get("DEM_CLAUDE_AI_COMMAND", "claude")
    # Windows の npm shim は `claude.cmd` なので、PATHEXT を見て実体のパスに解決する。
    return shutil.which(name) or name


def _model() -> str:
    return os.environ.get("DEM_CLAUDE_AI_MODEL", _DEFAULT_MODEL)


def _effort() -> str:
    return os.environ.get("DEM_CLAUDE_AI_EFFORT", _DEFAULT_EFFORT)


def _build_args(system: str | None, schema: dict | None, tools: tuple[str, ...] = ()) -> list[str]:
    args = [
        _command(), "-p",
        "--output-format", "json",
        "--tools", ",".join(tools),
        "--no-session-persistence",
    ]
    if tools:
        # -p では許可を尋ねられないので、渡した道具は先に許しておく(許さないと拒まれて使えない)。
        args += ["--allowedTools", ",".join(tools)]
    if system is not None:
        args += ["--system-prompt", system]
    if schema is not None:
        args += ["--json-schema", json.dumps(schema, ensure_ascii=False)]
    args += ["--model", _model(), "--effort", _effort()]
    return args


def _record_usage(result: dict) -> None:
    usage = result.get("usage") or {}
    _tally["calls"] += 1
    # input_tokens はキャッシュ命中分を含まないので、実際に読ませた量として足し合わせる。
    _tally["input_tokens"] += sum(
        int(usage.get(key) or 0)
        for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    _tally["output_tokens"] += int(usage.get("output_tokens") or 0)
    _tally["cost_usd"] += float(result.get("total_cost_usd") or 0.0)


def usage_summary() -> str:
    return (f"claude 呼び出し {_tally['calls']}回 / 入力 {_tally['input_tokens']} tok"
            f" / 出力 {_tally['output_tokens']} tok / ${_tally['cost_usd']:.4f}")


def generate(
    prompt: str,
    *,
    system: str | None = None,
    format: dict | str | None = None,
    timeout: float = 120.0,
    options: dict | None = None,
    tools: tuple[str, ...] = (),
) -> str:
    """`claude -p` に `prompt` を渡し、生成テキストを返す。

    `format` が JSON Schema の辞書なら `--json-schema` で構造化出力に制約し、
    その JSON を文字列にして返す(`"json"` は制約なしの素通し)。
    `options`(Ollama の temperature 等)は Claude Code に相当する設定が無いので受け取るだけで使わない。
    `tools` は使わせる道具(`"WebSearch"` など)。既定は道具なし。
    """
    schema = format if isinstance(format, dict) else None
    args = _build_args(system, schema, tools)
    # CLI の起動と思考のぶん、Ollama 向けの timeout(既定 120 秒)では足りないことがある。
    timeout = max(float(timeout), float(os.environ.get("DEM_CLAUDE_AI_TIMEOUT", 300)))
    # プロジェクトの CLAUDE.md・設定を拾わせない(生成の指示は system だけにする)。
    cwd = tempfile.gettempdir()
    try:
        completed = subprocess.run(
            args, input=prompt, capture_output=True, cwd=cwd,
            encoding="utf-8", errors="replace", timeout=timeout)
    except OSError as error:
        raise ClaudeAIError(f"Claude Code({args[0]})を起動できない: {error}") from error
    except subprocess.TimeoutExpired as error:
        raise ClaudeAIError(f"Claude Code が {timeout} 秒以内に応答しない") from error

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[-2000:]
        raise ClaudeAIError(
            f"Claude Code が終了コード {completed.returncode} で失敗: {detail}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ClaudeAIError(
            f"Claude Code の出力が JSON として読めない: {completed.stdout[-2000:]!r}") from error
    if not isinstance(result, dict):
        raise ClaudeAIError(f"Claude Code の出力が想定の形でない: {result!r}")

    _record_usage(result)
    if result.get("is_error") or result.get("subtype") != "success":
        raise ClaudeAIError(
            f"Claude Code がエラーを返した({result.get('subtype')}): {result.get('result')!r}")

    if schema is not None and result.get("structured_output") is not None:
        return json.dumps(result["structured_output"], ensure_ascii=False)
    text = result.get("result")
    if text is None:
        raise ClaudeAIError(f"Claude Code の応答に 'result' が無い: {result!r}")
    return text


def generate_json(
    prompt: str,
    schema: dict,
    *,
    system: str | None = None,
    timeout: float = 120.0,
    options: dict | None = None,
    tools: tuple[str, ...] = (),
) -> dict:
    """`generate` を `schema`(JSON Schema)で構造化出力に制約して呼び、パースした辞書を返す。"""
    text = generate(
        prompt, system=system, format=schema, timeout=timeout, options=options, tools=tools)
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ClaudeAIError(
            f"Claude Code の応答がJSONとしてパースできない: {text!r}") from error


def try_generate_json(
    prompt: str,
    schema: dict,
    *,
    system: str | None = None,
    timeout: float = 120.0,
    options: dict | None = None,
    tools: tuple[str, ...] = (),
) -> dict:
    """`generate_json` を試し、失敗(起動不可・応答がJSONとして壊れている)なら空の辞書を返す。"""
    try:
        return generate_json(prompt, schema, system=system, timeout=timeout, options=options, tools=tools)
    except ClaudeAIError as error:
        print(f"[claude_ai] Claude Code の応答が使えなかったため既定値で進める: {error}")
        return {}
