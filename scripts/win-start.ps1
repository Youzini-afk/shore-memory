param(
  [string]$BindHost = '127.0.0.1',
  [int]$ServerPort = 7811,
  [int]$WorkerPort = 7812
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$workerDir = Join-Path $root 'worker'
$serverDir = Join-Path $root 'server'
$webDist = Join-Path $root 'web\dist'
$dataDir = Join-Path $root 'data'
$workerPidFile = Join-Path $dataDir 'worker.pid'
$venvPython = Join-Path $workerDir '.venv\Scripts\python.exe'
$serverExe = Join-Path $serverDir 'target\release\shore-memory-server.exe'

if (-not (Test-Path $dataDir)) {
  New-Item -ItemType Directory -Path $dataDir | Out-Null
}

if (-not (Test-Path $venvPython)) {
  throw 'worker virtualenv not found. Run scripts\win-build.ps1 first.'
}

if (-not (Test-Path $serverExe)) {
  throw 'server release binary not found. Run scripts\win-build.ps1 first.'
}

$env:PMS_DATA_DIR = $dataDir

$workerCommand = 'Set-Location "{0}"; & "{1}" -m uvicorn app.main:app --host "{2}" --port {3}' -f $workerDir, $venvPython, $BindHost, $WorkerPort
$workerProcess = Start-Process powershell -ArgumentList '-NoExit', '-Command', $workerCommand -PassThru
Set-Content -Path $workerPidFile -Value $workerProcess.Id

$env:PMS_HOST = $BindHost
$env:PMS_PORT = [string]$ServerPort
$env:PMS_WEB_DIST = $webDist
$env:PMS_WORKER_BASE_URL = "http://${BindHost}:${WorkerPort}"

try {
  & $serverExe
} finally {
  try {
    if (-not $workerProcess.HasExited) {
      Stop-Process -Id $workerProcess.Id -Force -ErrorAction Stop
    }
  } catch {
  }
  Remove-Item $workerPidFile -ErrorAction SilentlyContinue
}
