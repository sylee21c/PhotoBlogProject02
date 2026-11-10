$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& '.\.venv\Scripts\python.exe' PhotoBlogServer/run_tests.py
exit $LASTEXITCODE
