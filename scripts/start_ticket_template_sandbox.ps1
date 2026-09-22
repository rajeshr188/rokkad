param([ValidateRange(1024, 65535)][int]$Port = 8082)
$ErrorActionPreference = 'Stop'
$ticketRoot = Split-Path -Parent $PSScriptRoot
$ticketPython = Join-Path $ticketRoot '..\..\.venv314\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $ticketPython)) { throw 'The shared .venv314 Python environment is required.' }
if (-not (Test-Path -LiteralPath (Join-Path $ticketRoot 'outputs\ticket-template-sandbox\runtime.json'))) {
    throw 'Provision the isolated ticket sandbox first; see docs/plans/ticket-template-designer.md.'
}
Set-Location -LiteralPath $ticketRoot
& $ticketPython manage.py runserver "127.0.0.1:$Port" --noreload --settings django_project.settings.ticket_template_sandbox
exit $LASTEXITCODE
