#Requires -RunAsAdministrator
# ============================================================
# Knoa one-click deploy (Windows Server 2016 / Tencent Cloud transition, 2C2G)
# Run as ADMIN PowerShell on the server.
#   .\00-deploy.ps1                # HTTP mode (pure-IP access, no cert needed)
#   .\00-deploy.ps1 -Tls           # HTTPS + self-signed cert (needs openssl)
#   .\00-deploy.ps1 -Rotate        # also regenerate JWT_SECRET / ADMIN_PASSWORD
#   .\00-deploy.ps1 -PublicIP 1.2.3.4
# Step 1 installs Docker + Hyper-V then REBOOTS. After reboot, re-run this
# same script as Admin; finished steps are skipped (idempotent).
# ============================================================
[CmdletBinding()]
param(
    [switch]$Tls,
    [string]$PublicIP = "170.106.74.73",
    [switch]$Rotate
)

$ErrorActionPreference = "Stop"
$ROOT        = "C:\knoa"
$MIRROR      = "https://mirror.ccs.tencentyun.com"
$COMPOSE_VER = "v2.27.1"

$deployEnv   = "$ROOT\deploy\.env"
$deployTmpl  = "$ROOT\deploy\.env.production-template"
$beEnv       = "$ROOT\backend\.env"
$rootEnv     = "$ROOT\.env"
$certDir     = "$ROOT\deploy\nginx\certs"
$nginxConf   = "$ROOT\deploy\nginx\nginx.conf"
$nginxHttp   = "$ROOT\deploy\nginx\nginx.http.conf"

if ($Tls) { $Scheme = "https" } else { $Scheme = "http" }

function GenHex([int]$len) {
    $b = New-Object byte[] $len
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    ($b | ForEach-Object { $_.ToString("x2") }) -join ""
}

# ---- Step 1: Docker engine (install only if missing; reboot then re-run) ----
Write-Host "==> [1/9] Docker engine" -ForegroundColor Cyan
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "    docker already present, skip."
} else {
    Write-Host "    installing Docker + Hyper-V (machine will REBOOT)..."
    Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force -Confirm:$false | Out-Null
    Install-Module -Name DockerMsftProvider -Force -Confirm:$false -Scope AllUsers
    Install-Package -Name docker -ProviderName DockerMsftProvider -Force
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All -Force | Out-Null
    Write-Host ""
    Write-Host "Docker installed. Rebooting now." -ForegroundColor Yellow
    Write-Host "After reboot, re-open ADMIN PowerShell and run THIS script again." -ForegroundColor Yellow
    Restart-Computer -Force
    exit 0
}

# ---- Step 2: docker compose v2 ----
Write-Host "==> [2/9] docker compose v2" -ForegroundColor Cyan
$dest = "$Env:ProgramFiles\Docker\docker-compose.exe"
if (-not (Test-Path $dest)) {
    $url = "https://github.com/docker/compose/releases/download/$COMPOSE_VER/docker-compose-windows-x86_64.exe"
    Write-Host "    downloading $url"
    Invoke-WebRequest -Uri $url -OutFile $dest
}
docker compose version

# ---- Step 3: Tencent Cloud registry mirror ----
Write-Host "==> [3/9] registry mirror ($MIRROR)" -ForegroundColor Cyan
$daemonDir = "C:\ProgramData\Docker\config"
New-Item -ItemType Directory -Force -Path $daemonDir | Out-Null
@{ "registry-mirrors" = @($MIRROR) } | ConvertTo-Json | Set-Content "$daemonDir\daemon.json" -Encoding ASCII
Restart-Service docker
Start-Sleep -Seconds 5

# ---- Step 4: firewall 80/443/22 ----
Write-Host "==> [4/9] firewall 80/443/22" -ForegroundColor Cyan
New-NetFirewallRule -DisplayName "Knoa-HTTP-80"  -Direction Inbound -Protocol TCP -LocalPort 80  -Action Allow -ErrorAction SilentlyContinue | Out-Null
New-NetFirewallRule -DisplayName "Knoa-HTTPS-443" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow -ErrorAction SilentlyContinue | Out-Null
New-NetFirewallRule -DisplayName "Knoa-SSH-22"    -Direction Inbound -Protocol TCP -LocalPort 22  -Action Allow -ErrorAction SilentlyContinue | Out-Null

# ---- Step 5: project code (clone or reuse existing C:\knoa) ----
Write-Host "==> [5/9] project code" -ForegroundColor Cyan
if (Test-Path "$ROOT\.git") {
    Write-Host "    repo already at $ROOT, skip clone."
} else {
    if ((Test-Path $ROOT) -and (Get-ChildItem $ROOT -Force | Where-Object { $_.Name -ne 'deploy' })) {
        throw "C:\knoa exists and is not empty (except deploy\). Remove it manually before cloning."
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "git not found. Install Git for Windows first: https://git-scm.com/download/win"
    }
    git clone https://github.com/xuyawen/knoa.git $ROOT
}

# ---- Step 6: cert / certbot dirs ----
Write-Host "==> [6/9] cert directories" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $certDir, "$ROOT\deploy\nginx\certbot" | Out-Null

# ---- Step 7: nginx config (HTTP / HTTPS) ----
Write-Host "==> [7/9] nginx config ($Scheme)" -ForegroundColor Cyan
if ($Tls) {
    $key  = "$certDir\privkey.pem"
    $cert = "$certDir\fullchain.pem"
    if (-not ((Test-Path $key) -and (Test-Path $cert))) {
        if (-not (Get-Command openssl -ErrorAction SilentlyContinue)) {
            throw "openssl required for -Tls. Install it (choco install openssl) and re-run."
        }
        Write-Host "    generating self-signed cert (CN=$PublicIP)"
        openssl req -x509 -newkey rsa:2048 -keyout $key -out $cert -days 365 -nodes -subj "/CN=$PublicIP"
    }
    Write-Host "    using HTTPS nginx.conf (cert present)."
} else {
    if (-not (Test-Path $nginxHttp)) { throw "missing $nginxHttp" }
    Copy-Item $nginxHttp $nginxConf -Force
    Write-Host "    copied HTTP-only nginx.conf."
}

# ---- Step 8: env files (root .env feeds compose interpolation) ----
Write-Host "==> [8/9] environment (.env)" -ForegroundColor Cyan
$PG = GenHex(24)

# root .env: docker compose auto-loads it; provides CORS_ORIGINS / POSTGRES_PASSWORD / PUBLIC_IP
@(
    "POSTGRES_PASSWORD=$PG",
    "PUBLIC_IP=$PublicIP",
    "CORS_ORIGINS=${Scheme}://$PublicIP",
    "TLS_MODE=$Scheme"
) | Set-Content $rootEnv -Encoding UTF8

# deploy/.env (doc/compat)
if (-not (Test-Path $deployEnv)) {
    if (-not (Test-Path $deployTmpl)) { throw "template not found: $deployTmpl" }
    Copy-Item $deployTmpl $deployEnv
}
$c = Get-Content $deployEnv -Raw
$c = $c -replace 'POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$PG"
$c = $c -replace 'PUBLIC_IP=.*',         "PUBLIC_IP=$PublicIP"
$c = $c -replace 'CORS_ORIGINS=.*',      "CORS_ORIGINS=${Scheme}://$PublicIP"
$c = $c -replace 'TLS_MODE=.*',          "TLS_MODE=$Scheme"
Set-Content $deployEnv $c -Encoding UTF8

# backend/.env (mirror CORS; rotate secrets on request)
if (-not (Test-Path $beEnv)) { throw "backend/.env not found: $beEnv" }
$c2 = Get-Content $beEnv -Raw
$c2 = $c2 -replace 'CORS_ORIGINS=.*', "CORS_ORIGINS=${Scheme}://$PublicIP"
if ($Rotate) {
    $JWT = GenHex(32); $ADM = GenHex(16)
    $c2 = $c2 -replace 'JWT_SECRET=.*',      "JWT_SECRET=$JWT"
    $c2 = $c2 -replace 'ADMIN_PASSWORD=.*',  "ADMIN_PASSWORD=$ADM"
}
Set-Content $beEnv $c2 -Encoding UTF8

Write-Host "    POSTGRES_PASSWORD = $PG"
if ($Rotate) { Write-Host "    JWT_SECRET       = $JWT"; Write-Host "    ADMIN_PASSWORD   = $ADM  (user: admin)" }
else         { Write-Host "    JWT_SECRET / ADMIN_PASSWORD: kept existing values in backend/.env" }

# ---- Step 9: build + start + health check ----
Write-Host "==> [9/9] build + start" -ForegroundColor Cyan
Set-Location $ROOT
docker compose -f docker-compose.prod-lean.yml up -d --build

Write-Host "    waiting 35s for migration + healthcheck..."
Start-Sleep -Seconds 35

Write-Host "    container status:"
docker compose -f docker-compose.prod-lean.yml ps

Write-Host "    backend health (expect JSON with status ok):"
docker exec knoa-backend curl -fsS http://localhost:8000/api/health

Write-Host ""
Write-Host "Done. Open in browser:  ${Scheme}://$PublicIP" -ForegroundColor Green
Write-Host "Login: admin + ADMIN_PASSWORD (use -Rotate to regenerate, or reuse existing)." -ForegroundColor Green
