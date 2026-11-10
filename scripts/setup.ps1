$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ is required.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r PhotoBlogServer/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' PhotoBlogServer/manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
& '.\.venv\Scripts\python.exe' PhotoBlogServer/manage.py bootstrap_demo --no-images
if ($LASTEXITCODE -ne 0) { throw 'Demo initialization failed.' }
Write-Output 'Ready. Run scripts/start-server.ps1. Local credentials are in .runtime/demo-credentials.json.'
