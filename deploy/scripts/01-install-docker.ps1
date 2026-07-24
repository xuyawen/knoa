#Requires -RunAsAdministrator
# ============================================================
# 01-install-docker.ps1  (run on Windows Server 2016, will REBOOT)
# Installs Docker Engine (EE) for WS2016 + enables Hyper-V.
# After reboot, run 02-configure-host.ps1
# ============================================================
$ErrorActionPreference = "Stop"

Write-Host "[1/4] Installing NuGet provider ..."
Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force -Confirm:$false | Out-Null

Write-Host "[2/4] Installing DockerMsftProvider module ..."
Install-Module -Name DockerMsftProvider -Force -Confirm:$false -Scope AllUsers

Write-Host "[3/4] Installing docker engine package ..."
Install-Package -Name docker -ProviderName DockerMsftProvider -Force

Write-Host "[4/4] Enabling Hyper-V (required for containers) ..."
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All -Force | Out-Null

Write-Host ""
Write-Host "Docker Engine installed. The machine will now reboot."
Write-Host "After reboot, open an ADMIN PowerShell and run:"
Write-Host "    cd C:\knoa\deploy\scripts; .\02-configure-host.ps1"
Write-Host ""
Restart-Computer -Force
