#!/bin/bash
# core/.venv を作り、requirements.txt が変わったときだけ依存を入れ直す。何度回してもよい。
set -euo pipefail
cd "$(dirname "$0")"

[ -x .venv/bin/python ] || python3 -m venv .venv

stamp=.venv/.requirements.sha256
want=$(sha256sum requirements.txt | cut -d' ' -f1)
if [ "$(cat "$stamp" 2>/dev/null)" != "$want" ]; then
  .venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt
  echo "$want" > "$stamp"
fi
