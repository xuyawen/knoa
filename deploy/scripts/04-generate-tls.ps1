#Requires -RunAsAdministrator
# ============================================================
# 04-generate-tls.ps1  (run as Admin)
# Generates a self-signed TLS cert into deploy/nginx/certs/.
# Browsers will warn, but transport is encrypted. For a real
# cert use Let's Encrypt (see PRODUCTION.md section 二 / Step 6-B).
#
# Usage:
#   .\04-generate-tls.ps1                 # CN = 170.106.74.73
#   .\04-generate-tls.ps1 -CN knoa.example.com
# ============================================================
[CmdletBinding()]
param(
    [string]$CN = "170.106.74.73"
)

$ErrorActionPreference = "Stop"
$PROJECT_ROOT = "C:\knoa"
$CERT_DIR = "$PROJECT_ROOT\deploy\nginx\certs"
$KEY  = "$CERT_DIR\privkey.pem"
$CERT = "$CERT_DIR\fullchain.pem"

New-Item -ItemType Directory -Force -Path $CERT_DIR | Out-Null

if (-not (Get-Command openssl -ErrorAction SilentlyContinue)) {
    Write-Host "openssl not found on PATH." -ForegroundColor Yellow
    Write-Host "Install it, then re-run this script:"
    Write-Host "  choco install openssl   (if Chocolatey is present)"
    Write-Host "  or download from https://slproweb.com/products/Win32OpenSSL.html"
    Write-Host "  and add the bin dir to PATH."
    throw "openssl required"
}

if ((Test-Path $KEY) -and (Test-Path $CERT)) {
    Write-Host "Certificate already exists, skipping: $KEY / $CERT"
    exit 0
}

Write-Host "Generating self-signed cert (CN=$CN) -> $CERT_DIR"
openssl req -x509 -newkey rsa:2048 `
    -keyout $KEY -out $CERT `
    -days 365 -nodes -subj "/CN=$CN"

Write-Host "Done. nginx (edge) will pick up the cert on next 'docker compose up'."
