$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root 'data\worker.pid'

if (-not (Test-Path $pidFile)) {
  exit 0
}

$pidValue = (Get-Content $pidFile -Raw).Trim()
if ($pidValue) {
  try {
    Stop-Process -Id ([int]$pidValue) -Force -ErrorAction Stop
  } catch {
  }
}

Remove-Item $pidFile -ErrorAction SilentlyContinue
