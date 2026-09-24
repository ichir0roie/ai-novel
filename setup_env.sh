#!/bin/bash
# プロジェクトルート(世界リポジトリ直下)に .venv を作り、requirements.txt が変わったときだけ依存を入れ直す。何度回してもよい。
# Linux の bash と、Windows の Git Bash(Claude Code のフックもこれで動く)の両方で動く。
set -euo pipefail
cd "$(dirname "$0")"
venv=../.venv

if [ -x "$venv/Scripts/python.exe" ]; then
  py="$venv/Scripts/python.exe"
elif [ -x "$venv/bin/python" ]; then
  py="$venv/bin/python"
else
  "$(command -v python3 || command -v python)" -m venv "$venv"
  if [ -x "$venv/Scripts/python.exe" ]; then py="$venv/Scripts/python.exe"; else py="$venv/bin/python"; fi
fi

stamp="$venv/.requirements.sha256"
want=$(sha256sum requirements.txt | cut -d' ' -f1)
if [ "$(cat "$stamp" 2>/dev/null)" != "$want" ]; then
  "$py" -m pip install -q --disable-pip-version-check -r requirements.txt
  echo "$want" > "$stamp"
fi
