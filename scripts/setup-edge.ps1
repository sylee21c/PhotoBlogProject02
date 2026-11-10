$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$env:PYTHONUTF8 = '1'
if (-not (Test-Path -LiteralPath '.venv-edge/Scripts/python.exe')) {
    py -3.12 -m venv .venv-edge
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12, then run this script again.' }
}
$python = Join-Path $taskRoot '.venv-edge/Scripts/python.exe'
& $python -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }
& $python -m pip install -r YOLOv5/requirements-edge-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'YOLO dependencies failed.' }
$weights = Join-Path $taskRoot 'YOLOv5/yolov5s.pt'
if (-not (Test-Path -LiteralPath $weights)) {
    Invoke-WebRequest 'https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.pt' -OutFile $weights
}
$taskHasher = [Security.Cryptography.SHA256]::Create()
$taskStream = [IO.File]::OpenRead($weights)
try { $taskDigest = [BitConverter]::ToString($taskHasher.ComputeHash($taskStream)).Replace('-','') }
finally { $taskStream.Dispose(); $taskHasher.Dispose() }
if ($taskDigest -ne '8B3B748C1E592DDD8868022E8732FDE20025197328490623CC16C6F24D0782EE') {
    throw 'Official model checksum mismatch. Do not run this weights file.'
}
Write-Output 'Ready. Run scripts/start-yolo.ps1 -Baseline for the unchanged detector.'
