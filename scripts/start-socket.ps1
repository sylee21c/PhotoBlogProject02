$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'PhotoBlogServer')
& '..\.venv\Scripts\python.exe' -m tools.socket_capture --host 127.0.0.1 --port 8001
