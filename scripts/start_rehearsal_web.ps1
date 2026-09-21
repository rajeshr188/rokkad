param(
    [Parameter(Mandatory = $true)][string]$DatabaseName,
    [ValidateRange(1024, 65535)][int]$Port = 8081
)
$ErrorActionPreference = 'Stop'
if ($DatabaseName -notmatch '^rokkad_baseline_rehearsal_[A-Za-z0-9_]+$') {
    throw 'Select an isolated rokkad_baseline_rehearsal_ database.'
}
$rehearsalRoot = Split-Path -Parent $PSScriptRoot
$rehearsalPython = Join-Path $rehearsalRoot '.venv314\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $rehearsalPython)) { throw 'The .venv314 Python environment is required.' }
$env:ROKKAD_REHEARSAL_DB_NAME = $DatabaseName
Set-Location -LiteralPath $rehearsalRoot
& $rehearsalPython manage.py runserver "127.0.0.1:$Port" --noreload --settings django_project.settings.baseline_rehearsal_web
exit $LASTEXITCODE
