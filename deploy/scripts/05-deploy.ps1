#Requires -RunAsAdministrator
# ============================================================
# 05-deploy.ps1  (run as Admin, AFTER 01-04)
# Builds images and starts all services in the background,
# then waits and runs a health check.
# ============================================================
$ErrorActionPreference = "Stop"
$PROJECT_ROOT = "C:\knoa"
$PUBLIC_IP    = "170.106.74.73"   # keep in sync with 03-setup-env.ps1 -PublicIP

Set-Location $PROJECT_ROOT

Write-Host "[1/3] Building and starting services (detached) ..."
docker compose -f docker-compose.prod-lean.yml up -d --build

Write-Host "[2/3] Waiting 35s for backend migration + healthcheck ..."
Start-Sleep -Seconds 35

Write-Host "[3/3] Container status:"
docker compose -f docker-compose.prod-lean.yml ps

Write-Host ""
Write-Host "Health check (expect JSON with status ok):"
curl.exe -k "https://$PUBLIC_IP/api/health"
Write-Host ""

Write-Host "If backend shows 'restarting', inspect logs:"
Write-Host "  docker compose -f docker-compose.prod-lean.yml logs backend"
Write-Host ""
Write-Host "Open the app in a browser:  https://$PUBLIC_IP"
Write-Host "Login with admin + the ADMIN_PASSWORD from 03-setup-env.ps1 (change it after first login)."
