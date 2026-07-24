#Requires -RunAsAdministrator
# ============================================================
# 03-setup-env.ps1  (run as Admin, AFTER repo is cloned)
# Generates strong secrets, copies deploy/.env from template,
# and fills deploy/.env + backend/.env with real values.
#
# Usage:
#   .\03-setup-env.ps1                       # fill .env, keep existing JWT/ADMIN
#   .\03-setup-env.ps1 -PublicIP 1.2.3.4     # custom public IP
#   .\03-setup-env.ps1 -Rotate               # also regenerate JWT_SECRET + ADMIN_PASSWORD
# ============================================================
[CmdletBinding()]
param(
    [string]$PublicIP = "170.106.74.73",
    [switch]$Rotate
)

$ErrorActionPreference = "Stop"
$PROJECT_ROOT = "C:\knoa"
$deployEnv    = "$PROJECT_ROOT\deploy\.env"
$deployTmpl   = "$PROJECT_ROOT\deploy\.env.production-template"
$beEnv        = "$PROJECT_ROOT\backend\.env"

function GenHex([int]$len) {
    $b = New-Object byte[] $len
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    ($b | ForEach-Object { $_.ToString("x2") }) -join ""
}

# --- deploy/.env ---
if (-not (Test-Path $deployEnv)) {
    if (-not (Test-Path $deployTmpl)) { throw "template not found: $deployTmpl" }
    Copy-Item $deployTmpl $deployEnv
}
$POSTGRES_PW = GenHex(24)
$c = Get-Content $deployEnv -Raw
$c = $c -replace 'POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$POSTGRES_PW"
$c = $c -replace 'PUBLIC_IP=.*',         "PUBLIC_IP=$PublicIP"
$c = $c -replace 'CORS_ORIGINS=.*',      "CORS_ORIGINS=https://$PublicIP"
$c = $c -replace 'TLS_MODE=.*',          "TLS_MODE=https"
Set-Content $deployEnv $c -Encoding UTF8

# --- backend/.env (mirror CORS; rotate secrets only on request) ---
if (-not (Test-Path $beEnv)) { throw "backend/.env not found: $beEnv" }
$c2 = Get-Content $beEnv -Raw
$c2 = $c2 -replace 'CORS_ORIGINS=.*', "CORS_ORIGINS=https://$PublicIP"

if ($Rotate) {
    $JWT = GenHex(32)
    $ADM = GenHex(16)
    $c2 = $c2 -replace 'JWT_SECRET=.*',    "JWT_SECRET=$JWT"
    $c2 = $c2 -replace 'ADMIN_PASSWORD=.*', "ADMIN_PASSWORD=$ADM"
}
Set-Content $beEnv $c2 -Encoding UTF8

Write-Host "=== Generated credentials (SAVE THESE) ==="
Write-Host "POSTGRES_PASSWORD = $POSTGRES_PW"
if ($Rotate) {
    Write-Host "JWT_SECRET       = $JWT"
    Write-Host "ADMIN_PASSWORD   = $ADM  (login user: admin)"
} else {
    Write-Host "JWT_SECRET / ADMIN_PASSWORD: kept existing values in backend/.env"
}
Write-Host ""
Write-Host "deploy/.env and backend/.env are ready."
Write-Host "Next: .\04-generate-tls.ps1  (or skip for plain HTTP), then .\05-deploy.ps1"
