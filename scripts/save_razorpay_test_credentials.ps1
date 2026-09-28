# Interactive Windows-only setup. Secrets never enter command arguments or logs.
$ErrorActionPreference = 'Stop'
$credentialDirectory = Join-Path $env:LOCALAPPDATA 'Rokkad\private'
$credentialPath = Join-Path $credentialDirectory 'razorpay-test.xml'
$resultPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'outputs\razorpay-test-key-status.json'

function Write-SetupStatus([string]$Status) {
    $resultDirectory = Split-Path -Parent $resultPath
    New-Item -ItemType Directory -Path $resultDirectory -Force | Out-Null
    @{ status = $Status; at_utc = [DateTime]::UtcNow.ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
}

try {
    Write-SetupStatus 'awaiting_input'
    if (Test-Path -LiteralPath $credentialPath) {
        Write-SetupStatus 'existing_file_review_required'
        Write-Host 'A saved test credential already exists. No overwrite was performed.'
        exit 1
    }
    $credential = Get-Credential -Message 'Rokkad TEST setup: User name = Razorpay Test Key ID; Password = Key Secret. Do not enter live keys.'
    if ($null -eq $credential) {
        Write-SetupStatus 'cancelled'
        exit 1
    }
    if ($credential.UserName -cnotmatch '^rzp_test_[A-Za-z0-9]+$' -or $credential.Password.Length -eq 0) {
        Write-SetupStatus 'test_credentials_required'
        Write-Host 'Only a Razorpay test key and a nonempty secret are accepted. Nothing was saved.'
        exit 1
    }
    Write-SetupStatus 'verifying'
    # Only the provider's fixed HTTPS API endpoint receives the credential.
    # Do not follow redirects or print response bodies / exception details.
    $plainSecret = $credential.GetNetworkCredential().Password
    $basicBytes = [Text.Encoding]::UTF8.GetBytes($credential.UserName + ':' + $plainSecret)
    $authorization = 'Basic ' + [Convert]::ToBase64String($basicBytes)
    $plainSecret = $null
    [Array]::Clear($basicBytes, 0, $basicBytes.Length)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Method Get `
            -Uri 'https://api.razorpay.com/v1/payments?count=1' `
            -Headers @{ Authorization = $authorization } -MaximumRedirection 0 -TimeoutSec 30
        if ($response.StatusCode -ne 200) { throw 'Unexpected response' }
        $payload = $response.Content | ConvertFrom-Json
        if ($payload.entity -ne 'collection' -or $null -eq $payload.items) { throw 'Unexpected response' }
    } catch {
        Write-SetupStatus 'verification_failed'
        Write-Host 'Test API verification failed. Nothing was saved; check the keys or network and retry.'
        exit 1
    } finally {
        $authorization = $null
        $response = $null
        $payload = $null
    }
    New-Item -ItemType Directory -Path $credentialDirectory -Force | Out-Null
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object Security.AccessControl.FileSystemAccessRule(
        $sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $credentialDirectory -AclObject $acl
    # Export-Clixml protects the SecureString with Windows DPAPI for this user.
    $credential | Export-Clixml -LiteralPath $credentialPath -NoClobber
    $credential = $null
    Write-SetupStatus 'verified_and_saved'
    Write-Host 'Test API authentication succeeded. Credentials saved with Windows encryption outside OneDrive. No payment was created.'
} catch {
    Write-SetupStatus 'setup_failed'
    Write-Host 'Private credential setup could not finish. No exception details were logged.'
    exit 1
}
