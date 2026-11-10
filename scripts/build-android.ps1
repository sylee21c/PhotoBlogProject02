$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskSdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
if (-not (Test-Path -LiteralPath $taskSdk)) { throw 'Install Android SDK 35 and set ANDROID_HOME.' }
$taskHash = [Security.Cryptography.SHA256]::Create()
try { $taskDigest = [BitConverter]::ToString($taskHash.ComputeHash([Text.Encoding]::UTF8.GetBytes($taskRoot))).Replace('-','').Substring(0,12) } finally { $taskHash.Dispose() }
$env:PHOTOVIEWER_BUILD_ROOT = Join-Path ([IO.Path]::GetTempPath()) "PhotoViewerBuild-$taskDigest"
Set-Location -LiteralPath (Join-Path $taskRoot 'PhotoViewer')
[IO.File]::WriteAllText((Join-Path (Get-Location) 'local.properties'), 'sdk.dir=' + $taskSdk.Replace('\','/'))
& '.\gradlew.bat' --no-daemon assembleDebug testDebugUnitTest
if ($LASTEXITCODE -ne 0) { throw 'Android build or tests failed.' }
New-Item -ItemType Directory -Path (Join-Path $taskRoot 'artifacts') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $env:PHOTOVIEWER_BUILD_ROOT 'app\outputs\apk\debug\app-debug.apk') -Destination (Join-Path $taskRoot 'artifacts\PhotoViewer-debug.apk') -Force
Copy-Item -LiteralPath (Join-Path $env:PHOTOVIEWER_BUILD_ROOT 'app\reports\tests\testDebugUnitTest') -Destination (Join-Path $taskRoot 'evidence\android-unit-tests') -Recurse -Force
Write-Output 'APK: artifacts/PhotoViewer-debug.apk'
