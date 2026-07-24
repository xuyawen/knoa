#Requires -RunAsAdministrator
# ============================================================
# 02-configure-host.ps1  (run AFTER reboot, as Admin)
# Verifies docker, installs compose v2, sets Tencent Cloud mirror,
# opens firewall, clones the repo, creates cert dirs.
# ============================================================
$ErrorActionPreference = "Stop"

$PROJECT_ROOT = "C:\knoa"
$MIRROR       = "https://mirror.ccs.tencentyun.com"
$COMPOSE_VER  = "v2.27.1"

# 1. verify docker engine is up
Write-Host "[1/6] Verifying docker ..."
docker version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "docker engine not ready. Check 'Get-Service docker'." }

# 2. install docker compose v2 binary next to docker.exe
Write-Host "[2/6] Installing docker compose $COMPOSE_VER ..."
$dest = "$Env:ProgramFiles\Docker\docker-compose.exe"
if (-not (Test-Path $dest)) {
    $url = "https://github.com/docker/compose/releases/download/$COMPOSE_VER/docker-compose-windows-x86_64.exe"
    Write-Host "  downloading $url"
    Invoke-WebRequest -Uri $url -OutFile $dest
}
docker compose version

# 3. configure Tencent Cloud registry mirror
Write-Host "[3/6] Configuring registry mirror ($MIRROR) ..."
$daemonDir = "C:\ProgramData\Docker\config"
New-Item -ItemType Directory -Force -Path $daemonDir | Out-Null
@"
{ "registry-mirrors": [ "$MIRROR" ] }
"@ | Set-Content "$daemonDir\daemon.json" -Encoding ASCII
Restart-Service docker
Start-Sleep -Seconds 5

# 4. firewall: allow HTTP/HTTPS/SSH inbound
Write-Host "[4/6] Opening firewall ports 80/443/22 ..."
New-NetFirewallRule -DisplayName "Knoa-HTTP-80"  -Direction Inbound -Protocol TCP -LocalPort 80  -Action Allow -ErrorAction SilentlyContinue | Out-Null
New-NetFirewallRule -DisplayName "Knoa-HTTPS-443" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow -ErrorAction SilentlyContinue | Out-Null
New-NetFirewallRule -DisplayName "Knoa-SSH-22"    -Direction Inbound -Protocol TCP -LocalPort 22  -Action Allow -ErrorAction SilentlyContinue | Out-Null

# 5. clone repo (git clone needs an empty target dir)
Write-Host "[5/6] Preparing project directory ..."
if (Test-Path "$PROJECT_ROOT\.git") {
    Write-Host "  repo already present at $PROJECT_ROOT, skipping clone."
} else {
    if ((Test-Path $PROJECT_ROOT) -and (Get-ChildItem $PROJECT_ROOT -Force | Where-Object { $_.Name -ne 'deploy' })) {
        throw "C:\knoa exists and is not empty (except deploy\). Remove it manually before cloning."
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "git not found. Install Git for Windows first: https://git-scm.com/download/win"
    }
    git clone https://github.com/xuyawen/knoa.git $PROJECT_ROOT
}

# 6. create cert/certbot dirs (not tracked by git)
Write-Host "[6/6] Creating nginx cert directories ..."
New-Item -ItemType Directory -Force -Path "$PROJECT_ROOT\deploy\nginx\certs"   | Out-Null
New-Item -ItemType Directory -Force -Path "$PROJECT_ROOT\deploy\nginx\certbot" | Out-Null

Write-Host ""
Write-Host "Host configured. Next steps:"
Write-Host "  - (TLS)        .\03-setup-env.ps1      # generate secrets + fill .env"
Write-Host "  - (TLS)        .\04-generate-tls.ps1   # self-signed cert (or skip for HTTP)"
Write-Host "  - (deploy)     .\05-deploy.ps1         # build + start all services"
