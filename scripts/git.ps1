# Limit the ownership exception to this one repository and this invocation.
# No global Git configuration or filesystem access permissions are changed.
$taskRoot = Split-Path -Parent $PSScriptRoot
& git.exe -c "safe.directory=$($taskRoot.Replace('\','/'))" -C $taskRoot @args
exit $LASTEXITCODE
