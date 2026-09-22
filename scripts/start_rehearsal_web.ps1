param(
    [Parameter(Mandatory = $true)][string]$DatabaseName,
    [ValidateRange(1024, 65535)][int]$Port = 8081,
    [string]$R2CredentialFile
)
$ErrorActionPreference = 'Stop'
if ($DatabaseName -notmatch '^rokkad_baseline_rehearsal_[A-Za-z0-9_]+$') {
    throw 'Select an isolated rokkad_baseline_rehearsal_ database.'
}
$rehearsalRoot = Split-Path -Parent $PSScriptRoot
$rehearsalPython = Join-Path $rehearsalRoot '.venv314\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $rehearsalPython)) { throw 'The .venv314 Python environment is required.' }
$env:ROKKAD_REHEARSAL_DB_NAME = $DatabaseName
$rehearsalSettings = 'django_project.settings.baseline_rehearsal_web'
if ($R2CredentialFile) {
    if (-not (Test-Path -LiteralPath $R2CredentialFile -PathType Leaf)) { throw 'The protected R2 credential file is required.' }
    $env:ROKKAD_REHEARSAL_R2_CREDENTIALS = (Resolve-Path -LiteralPath $R2CredentialFile).Path
    $rehearsalSettings = 'django_project.settings.rehearsal_r2'
}
Set-Location -LiteralPath $rehearsalRoot
& $rehearsalPython manage.py runserver "127.0.0.1:$Port" --noreload --settings $rehearsalSettings
exit $LASTEXITCODE
