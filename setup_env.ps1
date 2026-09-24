# Windows(PowerShell)用。setup_env.sh と同じく .venv を作り、requirements.txt が変わったときだけ依存を入れ直す。
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { python -m venv .venv }

$stamp = ".venv\.requirements.sha256"
$want = (Get-FileHash requirements.txt -Algorithm SHA256).Hash.ToLower()
$have = if (Test-Path $stamp) { (Get-Content $stamp -Raw).Trim() } else { "" }
if ($have -ne $want) {
    & $py -m pip install -q --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Set-Content $stamp $want -NoNewline
}
