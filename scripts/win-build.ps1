$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$workerDir = Join-Path $root 'worker'
$webDir = Join-Path $root 'web'
$serverDir = Join-Path $root 'server'
$dataDir = Join-Path $root 'data'
$venvDir = Join-Path $workerDir '.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'

if (-not (Test-Path $dataDir)) {
  New-Item -ItemType Directory -Path $dataDir | Out-Null
}

Push-Location $webDir
if (Get-Command corepack -ErrorAction SilentlyContinue) {
  corepack enable
}
pnpm install --frozen-lockfile
pnpm build
Pop-Location

Push-Location $serverDir
cargo build --release
Pop-Location

if (-not (Test-Path $venvPython)) {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.11 -m venv $venvDir
  } elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv $venvDir
  } else {
    throw 'Python 3.11+ is required.'
  }
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $workerDir 'requirements.txt')
