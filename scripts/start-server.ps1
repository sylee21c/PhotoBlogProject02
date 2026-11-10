param([int]$Port = 8002)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& '.\.venv\Scripts\python.exe' PhotoBlogServer/manage.py runserver "0.0.0.0:$Port"
