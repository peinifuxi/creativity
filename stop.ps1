Set-Location -Path $PSScriptRoot

$listeners = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue

if (-not $listeners) {
    Write-Output 'No service is listening on port 5000.'
    exit 0
}

$pids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $pids) {
    try {
        Stop-Process -Id $procId -Force -ErrorAction Stop
        Write-Output ("Stopped process PID={0}" -f $procId)
    }
    catch {
        Write-Warning ("Failed to stop PID={0}. {1}" -f $procId, $_.Exception.Message)
    }
}
