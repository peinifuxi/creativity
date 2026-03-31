Set-Location -Path $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$pythonCommand = $null

if (Test-Path $venvPython) {
    $pythonCommand = @($venvPython)
    Write-Output "Using virtual environment Python: $venvPython"
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = @("py", "-3.10")
    Write-Output "Using Python Launcher: py -3.10"
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = @("python")
    Write-Output "Using system Python from PATH"
}
else {
    Write-Error "Python not found. Please install Python 3.10.11 or create .venv first."
    exit 1
}

$listener = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Output 'Port 5000 is occupied, running stop.ps1 first.'
    & "$PSScriptRoot/stop.ps1"
}

Write-Output 'Starting app at http://127.0.0.1:5000'
if ($pythonCommand.Count -gt 1) {
    & $pythonCommand[0] $pythonCommand[1] "$PSScriptRoot/run.py"
}
else {
    & $pythonCommand[0] "$PSScriptRoot/run.py"
}
