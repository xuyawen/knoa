# dev.ps1 — Knoa 本地前后端一键启动 / 重启脚本（dev.sh 的 PowerShell 移植）
#
# 用法（PowerShell，非管理员上下文）：
#   powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1            # 智能模式：Docker 没开就拉起；前后端在跑就重启，没跑就启动
#   powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 start      # 同上
#   powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 restart    # 强制杀掉前后端后重新拉起
#   powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 stop       # 只停前后端（不动 Docker）
#   powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 status     # 探活
#   powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 backend    # 仅重启后端（改后端代码后用，不动 Docker/前端）
#
# 前台托管（与 dev.sh 一致）：
#   - start / restart 启动完服务后脚本保持前台运行（会话不中断），并给出交互式菜单：
#     可在同一会话输入命令重启后端/前端、看状态、看日志；输入 q 或按 Ctrl+C 才停服务退出
#
# 说明：
#   - 后端 uvicorn 不带 --reload，改了 .py 必须重启才生效（backend 模式即为此设）
#   - 后端纯 HTTP，host 0.0.0.0:8000；前端 vite dev :5175（/api 代理到后端）
#   - Postgres(5433) + Redis 由 Docker 本地起；Docker Desktop 没开本脚本会自动启动它
#   - 智能重启按「端口是否被占」判定：只要端口被占就先杀再起，绝不并存第二个实例
#
# 约定：开发后端请在普通（非管理员）终端启动。若用管理员终端启动，本脚本（普通权限）
#       无权停止它，会再现 netstat 看得见、taskkill 杀不掉的「幽灵进程」。

param(
    [string]$Mode = "start"
)

# 控制台按 UTF-8 输出，避免默认 GBK 代码页把中文日志显示成乱码
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }

# 脚本放在 scripts/ 下，项目根目录是其上一级
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$VenvPy = Join-Path $Backend ".venv\Scripts\python.exe"
$BPort = 8000
$FPort = 5175
$LogDir = Join-Path $Root ".devlogs"
$BackendLog = Join-Path $LogDir "backend.log"
$BackendErr = Join-Path $LogDir "backend.err.log"
$BackendPid = Join-Path $LogDir "backend.pid"
$FrontendLog = Join-Path $LogDir "frontend.log"
$FrontendErr = Join-Path $LogDir "frontend.err.log"
$FrontendPid = Join-Path $LogDir "frontend.pid"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Say($msg, $color = "Gray") { Write-Host "[dev] $msg" -ForegroundColor $color }

# 脚本自身诊断日志：追加到 .devlogs/dev.log（带时间戳），专记探活/等待/状态过程。
# 目的：服务卡住/未就绪时，翻 dev.log 就能看到每次探活返回什么（404/连不上/超时），
# 不必再临时写诊断脚本复现。
$DevLog = Join-Path $LogDir "dev.log"
function Log-File([string]$msg) {
    try { "$([DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss')) [dev] $msg" | Out-File $DevLog -Encoding utf8 -Append } catch { }
}
# 控制台 + 文件双写：关键节点（启动/就绪/失败）既看得见也留痕
function Say-Log($msg, $color = "Gray") { Say $msg $color; Log-File $msg }

# 杀掉占用指定端口的进程（按端口定位，杀整个进程树）
function Kill-Port([int]$Port) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { return }
    $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $procIds) {
        if ($procId -eq 0) { continue }
        Say "kill PID $procId on port $Port" "Yellow"
        taskkill /F /PID $procId /T 2>&1 | Out-Null
    }
    Start-Sleep -Seconds 1
}

# 探活指定端口的 http 服务，返回状态码字符串（连不上返回空串）
# host 默认 127.0.0.1；前端 vite 5 只听 IPv6 ::1，须用 localhost（由系统解析到 ::1）才能连通
function Probe([int]$Port, [string]$Path = "/", [string]$Host_ = "127.0.0.1") {
    try {
        $r = Invoke-WebRequest -Uri "http://$Host_`:$Port$Path" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        return [string]$r.StatusCode
    } catch {
        $resp = $_.Exception.Response
        if ($resp) {
            $c = [string][int]$resp.StatusCode
            # 探到非 200（如探错路径恒 404）：记下，这正是「服务在跑但探不中」的关键线索
            if ($c -ne "200") { Log-File "probe http://${Host_}:${Port}${Path} -> HTTP $c" }
            return $c
        }
        # 连不上（端口没监听 / 地址族不匹配 / 超时）：记下原因，区别于「探到错误码」
        Log-File "probe http://${Host_}:${Port}${Path} -> 连接失败 ($($_.Exception.Message))"
        return ""
    }
}

# 轮询等 http 服务返回 200（最多 $Seconds 秒）。复用 Probe（Invoke-WebRequest，自带 IPv4/IPv6 回退）：
# vite 只听 IPv6 ::1、后端只听 IPv4 127.0.0.1，裸 TcpClient 会因地址族不匹配干等超时，走 HTTP 探测才能正确连通
function Wait-UrlReady([string]$Host_, [int]$Port, [string]$Path = "/", [int]$Seconds = 20) {
    Log-File "wait http://${Host_}:${Port}${Path} 开始（上限 ${Seconds}s，每秒探活一次）"
    for ($i = 0; $i -lt $Seconds; $i++) {
        $code = Probe $Port $Path $Host_
        if ($code -eq "200") { Log-File "wait http://${Host_}:${Port}${Path} 就绪（$($i + 1)s）"; return $true }
        Start-Sleep -Seconds 1
        if ((($i + 1) % 5) -eq 0) { Say "  仍在等待，已 $($i + 1)s（每秒探活一次，就绪即继续，上限 ${Seconds}s）" "DarkGray" }
    }
    Log-File "wait http://${Host_}:${Port}${Path} ${Seconds}s 超时未就绪"
    return $false
}

# 等端口可连（最多 $Seconds 秒）
function Wait-Port([string]$Host_, [int]$Port, [int]$Seconds = 30) {
    for ($i = 0; $i -lt $Seconds; $i++) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $tcp.Connect($Host_, $Port)
            $tcp.Close()
            return $true
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

# 等端口释放（最多 10s）；用于重启前确认旧进程已退出
function Wait-PortFree([int]$Port) {
    for ($i = 0; $i -lt 10; $i++) {
        if (-not (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

# 确保 Docker Desktop 已运行：没开就拉起并等到引擎就绪
function Ensure-Docker {
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { return }
    Say "Docker Desktop 未运行，尝试启动 ..." "Yellow"
    $exe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $exe)) {
        Say "未找到 Docker Desktop ($exe)，请手动启动后再跑" "Red"
        exit 1
    }
    Start-Process $exe
    Say "等待 Docker 引擎就绪 (最多 ~90s) ..." "Yellow"
    for ($i = 0; $i -lt 45; $i++) {
        docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Say "Docker 已就绪" "Green"; return }
        Start-Sleep -Seconds 2
    }
    Say "Docker 在 90s 内未就绪，请检查 Docker Desktop 状态" "Red"
    exit 1
}

function Start-Deps {
    Ensure-Docker
    Say "起 Postgres + Redis" "Green"
    Push-Location $Root
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis
    Pop-Location
    Say "等 Postgres(5433) 就绪 ..." "Yellow"
    if (Wait-Port "127.0.0.1" 5433 30) {
        Say "Postgres 已就绪" "Green"
    } else {
        Say "30s 内没连上 5433，后端可能起不来；直接重试本脚本即可" "Yellow"
    }
}

function Start-Backend {
    if (-not (Test-Path $VenvPy)) { Say "找不到 venv Python：$VenvPy（请先在 backend 下 uv sync）" "Red"; exit 1 }
    Say "启动后端 (:$BPort)" "Green"
    Remove-Item $BackendLog, $BackendErr -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath $VenvPy `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$BPort") `
        -WorkingDirectory $Backend `
        -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErr `
        -WindowStyle Hidden -PassThru
    $script:BackendProc = $p
    "$($p.Id)" | Out-File $BackendPid -Encoding ascii -NoNewline
}

function Start-Frontend {
    Say "启动前端 (:$FPort)" "Green"
    Remove-Item $FrontendLog, $FrontendErr -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath "cmd.exe" `
        -ArgumentList @("/c", "npm", "run", "dev") `
        -WorkingDirectory $Frontend `
        -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErr `
        -WindowStyle Hidden -PassThru
    $script:FrontendProc = $p
    "$($p.Id)" | Out-File $FrontendPid -Encoding ascii -NoNewline
}

# 智能：端口被占用就杀掉重启，没占用就启动（绝不并存第二个实例，与 dev.sh 一致）
function Ensure-Backend {
    if (Get-NetTCPConnection -LocalPort $BPort -State Listen -ErrorAction SilentlyContinue) {
        Say "$BPort 已被占用，重启中 ..." "Yellow"
        Kill-Port $BPort
        if (-not (Wait-PortFree $BPort)) { Say "$BPort 仍被占用，后端可能启动失败" "Yellow" }
    }
    Start-Backend
}

function Ensure-Frontend {
    if (Get-NetTCPConnection -LocalPort $FPort -State Listen -ErrorAction SilentlyContinue) {
        Say "$FPort 已被占用，重启中 ..." "Yellow"
        Kill-Port $FPort
        if (-not (Wait-PortFree $FPort)) { Say "$FPort 仍被占用，vite 可能改用其他端口" "Yellow" }
    }
    Start-Frontend
}

function Stop-All {
    Say "停止前后端" "Green"
    Kill-Port $BPort
    Kill-Port $FPort
    foreach ($pidFile in @($BackendPid, $FrontendPid)) {
        if (Test-Path $pidFile) {
            $procId = (Get-Content $pidFile -Raw).Trim()
            if ($procId) { taskkill /F /PID $procId /T 2>&1 | Out-Null }
        }
    }
    Remove-Item $BackendPid, $FrontendPid -ErrorAction SilentlyContinue
}

# 前台托管退出清理：停掉本次启动的前后端（Ctrl+C / 服务崩溃退出都会触发）
function Stop-Service {
    Say "收到结束信号，停止前后端 ..." "Yellow"
    foreach ($proc in @($script:BackendProc, $script:FrontendProc)) {
        if ($proc -and -not $proc.HasExited) {
            taskkill /F /PID $proc.Id /T 2>&1 | Out-Null
        }
    }
    # 按端口兜底，确保 vite/uvicorn 的子进程也被清干净
    Kill-Port $BPort
    Kill-Port $FPort
    Remove-Item $BackendPid, $FrontendPid -ErrorAction SilentlyContinue
    Say "已停止前后端（Docker 数据库保留）" "Green"
}

# 交互式命令循环：服务在后台跑，前台可输入命令管理；q / Ctrl+C 退出并停服务
function Restart-BackendSvc {
    Kill-Port $BPort
    if (-not (Wait-PortFree $BPort)) { Say "$BPort 仍被占用，后端可能启动失败" "Yellow" }
    Start-Backend
    if (Wait-UrlReady "127.0.0.1" $BPort "/api/health" 90) { Say "后端已就绪" "Green" } else { Say "后端 90s 内未就绪，看 $BackendErr" "Yellow" }
}

function Restart-FrontendSvc {
    Kill-Port $FPort
    if (-not (Wait-PortFree $FPort)) { Say "$FPort 仍被占用，vite 可能改用其他端口" "Yellow" }
    Start-Frontend
    if (Wait-UrlReady "localhost" $FPort "/" 20) { Say "前端已就绪" "Green" } else { Say "前端 20s 内未就绪，看 $FrontendLog" "Yellow" }
}

function Show-Logs {
    Say "后端最近日志（$BackendLog）：" "Green"
    if (Test-Path $BackendLog) { Get-Content $BackendLog -Tail 20 } else { Say "（无日志）" "Yellow" }
    Say "前端最近日志（$FrontendLog）：" "Green"
    if (Test-Path $FrontendLog) { Get-Content $FrontendLog -Tail 20 } else { Say "（无日志）" "Yellow" }
}

# 等前后端就绪后再继续（初始启动用，避免服务还没起来就打印「未就绪」状态）
function Wait-ServicesReady {
    if (Wait-UrlReady "127.0.0.1" $BPort "/api/health" 90) { Say "后端已就绪" "Green" } else { Say "后端 90s 内未就绪，看 $BackendErr" "Yellow" }
    if (Wait-UrlReady "localhost" $FPort "/" 20) { Say "前端已就绪" "Green" } else { Say "前端 20s 内未就绪，看 $FrontendLog" "Yellow" }
}

# 前台运行：交互式菜单；q / Ctrl+C / 服务退出时，finally 触发 Stop-Service
function Run-Foreground {
    Say "前后端已启动。输入命令管理，q 或 Ctrl+C 退出并停止服务：" "Green"
    try {
        while ($true) {
            Write-Host "  [1] 重启后端  [2] 重启前端  [3] 重启前后端  [4] 状态  [5] 看日志  [q] 退出"
            $cmd = ""
            try { $cmd = Read-Host "[dev] >" } catch { Say "会话结束，停止服务 ..." "Yellow"; break }
            switch ($cmd) {
                "1" { Restart-BackendSvc }
                "2" { Restart-FrontendSvc }
                "3" { Restart-BackendSvc; Restart-FrontendSvc }
                "4" { Show-Status }
                "5" { Show-Logs }
                "q" { Say "退出，停止服务 ..." "Yellow"; return }
                "Q" { Say "退出，停止服务 ..." "Yellow"; return }
                "" { }
                default { Say "未知命令：$cmd" "Yellow" }
            }
        }
    } finally {
        Stop-Service
    }
}

# 状态码翻译成中文
function Code-To-Text([string]$Code) {
    switch -Regex ($Code) {
        "^$"    { "未启动（端口无响应）"; break }
        "000"   { "未启动（端口无响应）"; break }
        "200"   { "运行中（健康）"; break }
        "^3"    { "运行中（HTTP $Code 重定向）"; break }
        "^[45]" { "运行中但异常（HTTP $Code）"; break }
        default { "未知状态（HTTP $Code）"; break }
    }
}

function Show-Status {
    $b = Probe $BPort "/api/health"
    $f = Probe $FPort "/" "localhost"
    Log-File "status 后端=$b 前端=$f"
    Say "后端  : http://localhost:${BPort}/api/health -> $(Code-To-Text $b)" "Green"
    Say "前端  : http://localhost:${FPort}/         -> $(Code-To-Text $f)" "Green"
    if ($b -eq "200" -and $f -eq "200") {
        Say "结论  : 前后端都在正常运行" "Green"
    } else {
        $not = @()
        if ($b -ne "200") { $not += "后端" }
        if ($f -ne "200") { $not += "前端" }
        Say "结论  : $($not -join '+') 未就绪（刚重启可能仍在启动，稍等再查；或看 .devlogs 日志）" "Yellow"
    }
}

# 仅重启后端并探活（改后端代码后用）
function Restart-BackendOnly {
    $code = Probe $BPort "/api/health"
    if ($code -eq "200") {
        Say "后端已在跑，重启中 ..." "Yellow"
        Kill-Port $BPort
        Start-Sleep -Seconds 1
    }
    Start-Backend
    Say "等待 /api/health 就绪 ..." "Yellow"
    $ok = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        $code = Probe $BPort "/api/health"
        if ($code -eq "200") { $ok = $true; break }
    }
    if ($ok) {
        Say "后端运行正常（/api/health=200）。新代码改动已生效。" "Green"
    } else {
        Say "20s 内 /api/health 未返回 200，请检查日志：$BackendLog 与 $BackendErr" "Red"
        exit 1
    }
}

switch ($Mode) {
    "start" {
        Start-Deps
        Ensure-Backend
        Ensure-Frontend
        Wait-ServicesReady
        Show-Status
        Run-Foreground
    }
    "restart" {
        Start-Deps
        Kill-Port $BPort
        Kill-Port $FPort
        Start-Sleep -Seconds 1
        Start-Backend
        Start-Frontend
        Wait-ServicesReady
        Show-Status
        Run-Foreground
    }
    "stop" { Stop-All }
    "status" { Show-Status }
    "backend" { Restart-BackendOnly }
    default {
        Write-Host "用法: dev.ps1 {start|restart|stop|status|backend}"
        exit 1
    }
}
