param(
    [string]$Source = '0',
    [switch]$Baseline,
    [double]$Confidence = 0.5,
    [int]$MaxFrames = 0
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:YOLOV5_CONFIG_DIR = Join-Path $taskRoot '.runtime/yolo-config'
$env:MPLCONFIGDIR = Join-Path $taskRoot '.runtime/matplotlib'
$env:YOLOv5_AUTOINSTALL = 'false'
$env:OMP_NUM_THREADS = '4'
$detector = Join-Path $taskRoot 'YOLOv5/detect.py'
$weights = Join-Path $taskRoot 'YOLOv5/yolov5s.pt'
if (-not (Test-Path -LiteralPath $weights)) { throw 'Run scripts/setup-edge.ps1 first.' }
if ($Baseline) {
    # Materialize a complete tree so the unchanged upstream script keeps its
    # normal relative imports and default paths.
    $baselineRoot = Join-Path $taskRoot '.runtime/baseline-yolov5'
    New-Item -ItemType Directory -Path $baselineRoot -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $taskRoot 'YOLOv5') -Force |
        Where-Object { $_.Name -notin @('baseline','runs','__pycache__','assessment_tests','yolov5s.pt') } |
        Copy-Item -Destination $baselineRoot -Recurse -Force
    $detector = Join-Path $baselineRoot 'detect.py'
    Copy-Item -LiteralPath (Join-Path $taskRoot 'YOLOv5/baseline/detect.py') -Destination $detector -Force
    $expected = (Get-Content -LiteralPath (Join-Path $taskRoot 'YOLOv5/UPSTREAM.json') -Raw | ConvertFrom-Json).original_detect_sha256
    $taskHasher = [Security.Cryptography.SHA256]::Create()
    $taskStream = [IO.File]::OpenRead($detector)
    try { $actual = [BitConverter]::ToString($taskHasher.ComputeHash($taskStream)).Replace('-','').ToLowerInvariant() }
    finally { $taskStream.Dispose(); $taskHasher.Dispose() }
    if ($expected -and $actual -ne $expected) { throw 'Baseline source checksum mismatch.' }
}
$extra = @()
if (-not $Baseline) { $extra = @('--max-frames', $MaxFrames) }
& (Join-Path $taskRoot '.venv-edge/Scripts/python.exe') $detector --weights $weights --source $Source --device cpu --conf-thres $Confidence --view-img --nosave --project (Join-Path $taskRoot '.runtime/detect') --name $(if ($Baseline) {'baseline'} else {'edge'}) --exist-ok @extra
exit $LASTEXITCODE
