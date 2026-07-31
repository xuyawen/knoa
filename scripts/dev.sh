#!/usr/bin/env bash
# Knoa 本地前后端一键启动 / 重启脚本（跨平台：Mac + Windows Git Bash）
# 用法:
#   ./dev.sh            # 智能模式：Docker 没开就拉起；前后端端口被占就杀掉重启，没占就启动
#   ./dev.sh start      # 同上（智能模式）
#   ./dev.sh restart    # 强制杀掉前后端后重新拉起
#   ./dev.sh stop       # 只停前后端（不动 Docker）
#   ./dev.sh status     # 探活
#   ./dev.sh backend    # 仅重启后端（改后端 .py 后用，不动 Docker/前端）
#
# 前台托管:
#   - start / restart 启动完服务后脚本保持前台运行（会话不中断），并给出交互式菜单：
#     可在同一会话输入命令重启后端/前端、看状态、看日志；输入 q 或按 Ctrl+C 才停服务退出
#
# 说明:
#   - 后端 uvicorn 没有 --reload，改了 .py 必须重启才生效（backend 模式即为此设）
#   - 后端纯 HTTP，host 0.0.0.0:8000；前端 vite dev :5175（/api 代理到后端）
#   - Postgres(5433) + Redis 由 Docker 本地起；Docker 引擎没开本脚本会自动启动它
#   - 平台自适应：Windows(Git Bash/MSYS) 用 taskkill + netstat；macOS 用 kill + lsof
#   - 智能重启按「端口是否被占」判定：只要端口被占就先杀再起，绝不并存第二个实例
#   - 约定：请在普通（非管理员）终端启动。若用管理员终端起后端，本脚本（普通权限）
#     可能无权停止它，会出现 netstat 看得见、却杀不掉的「幽灵进程」。

set -u

# 脚本放在 scripts/ 下，项目根目录是其上一级
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
BPORT=8000
FPORT=5175
LOG_DIR="$ROOT/.devlogs"

mkdir -p "$LOG_DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[dev]${NC} $*"; }
warn() { echo -e "${YELLOW}[dev]${NC} $*"; }
err()  { echo -e "${RED}[dev]${NC} $*"; }
# 脚本自身诊断日志：追加到 .devlogs/dev.log（带时间戳），专记探活/等待/状态过程。
# 服务卡住/未就绪时翻它就能看到每次探活返回什么（404/连不上/超时），不必再写诊断脚本复现。
devlog() { echo "$(date '+%Y-%m-%d %H:%M:%S') [dev] $*" >> "$LOG_DIR/dev.log" 2>/dev/null || true; }

# ---------- 平台检测（Windows Git Bash 报 MINGW*/MSYS*/CYGWIN*；Mac 报 Darwin）----------
OS_KIND="unix"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) OS_KIND="windows" ;;
  Darwin)               OS_KIND="mac" ;;
  *)                    OS_KIND="unix" ;;
esac

# venv python 路径：Windows 用 .venv/Scripts/python.exe；Mac/Unix 用 .venv/bin/python
if [ "$OS_KIND" = "windows" ]; then
  VENV_PY="$BACKEND/.venv/Scripts/python.exe"
else
  VENV_PY="$BACKEND/.venv/bin/python"
fi

# 列出监听指定端口的进程 PID（每行一个）
list_port_pids() {
  local port=$1
  if [ "$OS_KIND" = "windows" ]; then
    netstat -ano 2>/dev/null | grep -E ":$port +" | grep LISTENING | awk '{print $5}' | sort -u
  else
    # macOS / Linux：lsof 只输出 PID（-t），含 LISTEN 态
    lsof -ti "tcp:$port" 2>/dev/null | sort -u
  fi
}

# 杀掉占用指定端口的进程（含子进程/进程树）
kill_port() {
  local port=$1 pid
  local pids
  pids=$(list_port_pids "$port")
  [ -z "$pids" ] && return 0
  for pid in $pids; do
    [ "$pid" = "0" ] && continue
    warn "kill PID $pid on port $port"
    if [ "$OS_KIND" = "windows" ]; then
      # Git Bash/MSYS 会把 /PID /F /T 当成路径转成 C:/Program Files/Git/PID 导致 taskkill 静默失败，
      # 必须用双斜杠 //PID //F //T 绕过路径转换
      taskkill //PID "$pid" //F //T >/dev/null 2>&1 || true
    else
      # 先递归杀子进程，再杀父进程
      pkill -P "$pid" >/dev/null 2>&1 || true
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  done
  sleep 1
}

# 探活指定端口的 http 服务，返回状态码或空（host 默认 127.0.0.1，前端用 localhost 以兼容 IPv6）
probe() {
  local port=$1 path=${2:-/} host=${3:-127.0.0.1} code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://$host:$port$path" 2>/dev/null)
  # 探不到 200 就留痕：000=连不上（端口没监听/地址族不匹配/超时），其余=探到错误码（如探错路径恒 404）
  [ "$code" != "200" ] && devlog "probe http://$host:$port$path -> ${code:-000}"
  echo "$code"
}

# 等端口可连（最多 ~$3 秒，默认 30）；每 5s 打印一次进度，表明仍在逐秒探活
wait_port() {
  local host=$1 port=$2 secs=${3:-30} i
  for i in $(seq 1 "$secs"); do
    if (exec 3<>"/dev/tcp/$host/$port") 2>/dev/null; then
      exec 3>&-
      return 0
    fi
    sleep 1
    [ $((i % 5)) -eq 0 ] && log "  仍在等待，已 ${i}s（每秒探活一次，就绪即继续，上限 ${secs}s）"
  done
  return 1
}

# 端口是否已被监听（无论里面是什么服务）
port_listening() {
  local port=$1
  [ -n "$(list_port_pids "$port")" ]
}

# 等端口释放（最多 ~10s）；用于重启前确认旧进程已退出
wait_port_free() {
  local port=$1
  for _ in $(seq 1 10); do
    if ! port_listening "$port"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# 确保 Docker 引擎已运行：没开就拉起并等到就绪
ensure_docker() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  warn "Docker 未运行，尝试启动 ..."
  if [ "$OS_KIND" = "mac" ]; then
    if [ ! -d "/Applications/Docker.app" ]; then
      err "未找到 Docker Desktop（/Applications/Docker.app），请手动启动后再跑"
      exit 1
    fi
    open -a Docker >/dev/null 2>&1 || true
  else
    local exe="/c/Program Files/Docker/Docker/Docker Desktop.exe"
    if [ ! -x "$exe" ]; then
      err "未找到 Docker Desktop ($exe)，请手动启动后再跑"
      exit 1
    fi
    local win_exe
    win_exe=$(cygpath -w "$exe")
    cmd /c start "" "$win_exe" >/dev/null 2>&1 || true
  fi
  log "等待 Docker 引擎就绪 (最多 ~90s) ..."
  for _ in $(seq 1 45); do
    if docker info >/dev/null 2>&1; then
      log "Docker 已就绪"
      return 0
    fi
    sleep 2
  done
  err "Docker 在 90s 内未就绪，请检查 Docker Desktop 状态"
  exit 1
}

start_deps() {
  ensure_docker
  log "起 Postgres + Redis"
  ( cd "$ROOT" && docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis )
  log "等 Postgres(5433) 就绪 ..."
  if wait_port 127.0.0.1 5433; then
    log "Postgres 已就绪"
  else
    warn "30s 内没连上 5433，后端可能起不来；直接重试本脚本即可"
  fi
}

# venv 前置检查（对齐 dev.ps1：缺 python 给友好提示而非裸报错）
check_venv() {
  if [ ! -x "$VENV_PY" ]; then
    err "找不到 venv Python：$VENV_PY（请先在 backend 下 uv sync）"
    exit 1
  fi
}

# 智能：端口被占用就杀掉重启，没占用就启动（绝不并存第二个实例）
# 用 launch_*（子进程式）启动，以便 Ctrl+C 时能按 PID 可靠清理
ensure_backend() {
  if port_listening "$BPORT"; then
    warn "$BPORT 已被占用，重启中 ..."
    kill_port "$BPORT"
    wait_port_free "$BPORT" || warn "$BPORT 仍被占用，后端可能启动失败"
  fi
  launch_backend
}

ensure_frontend() {
  if port_listening "$FPORT"; then
    warn "$FPORT 已被占用，重启中 ..."
    kill_port "$FPORT"
    wait_port_free "$FPORT" || warn "$FPORT 仍被占用，vite 可能改用其他端口"
  fi
  launch_frontend
}

stop_all() {
  log "停止前后端"
  kill_port "$BPORT"
  kill_port "$FPORT"
  rm -f "$LOG_DIR/backend.pid" "$LOG_DIR/frontend.pid"
}

# ---------- 前台托管：服务作为脚本的后台子进程，Ctrl+C 时统一清理 ----------
BACKEND_PID=""
FRONTEND_PID=""

# 以后台子进程启动后端，并记录其 PID（供 Ctrl+C 清理；日志写 .devlogs）
launch_backend() {
  check_venv
  log "启动后端 (: $BPORT)"
  ( cd "$BACKEND" && exec "$VENV_PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$BPORT" ) \
      > "$LOG_DIR/backend.log" 2> "$LOG_DIR/backend.err.log" &
  BACKEND_PID=$!
  echo "$BACKEND_PID" > "$LOG_DIR/backend.pid"
}

# 以后台子进程启动前端，并记录其 PID
launch_frontend() {
  log "启动前端 (: $FPORT)"
  ( cd "$FRONTEND" && exec npm run dev ) \
      > "$LOG_DIR/frontend.log" 2> "$LOG_DIR/frontend.err.log" &
  FRONTEND_PID=$!
  echo "$FRONTEND_PID" > "$LOG_DIR/frontend.pid"
}

# 退出清理：停掉前后端（Ctrl+C / 脚本异常退出都会触发）
cleanup() {
  trap - INT TERM EXIT
  warn "收到结束信号，停止前后端 ..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" >/dev/null 2>&1 || true
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  sleep 1
  # 按端口兜底，确保 vite/uvicorn 的子进程也被清干净
  kill_port "$BPORT"
  kill_port "$FPORT"
  rm -f "$LOG_DIR/backend.pid" "$LOG_DIR/frontend.pid"
  log "已停止前后端（Docker 数据库保留，./dev.sh stop 同样不动它）"
  exit 0
}

# 交互式命令循环：服务在后台跑，前台可输入命令管理；q / Ctrl+C 退出并停服务
restart_backend() {
  kill_port "$BPORT"
  wait_port_free "$BPORT" || warn "$BPORT 仍被占用，后端可能启动失败"
  launch_backend
}

restart_frontend() {
  kill_port "$FPORT"
  wait_port_free "$FPORT" || warn "$FPORT 仍被占用，vite 可能改用其他端口"
  launch_frontend
}

show_logs() {
  log "后端最近日志（$LOG_DIR/backend.log）："
  tail -n 20 "$LOG_DIR/backend.log" 2>/dev/null || true
  log "前端最近日志（$LOG_DIR/frontend.log）："
  tail -n 20 "$LOG_DIR/frontend.log" 2>/dev/null || true
}

run_foreground() {
  # INT/TERM：Ctrl+C 主动结束；EXIT：服务崩溃或退出导致循环结束时也走 cleanup，避免留下孤儿服务
  trap cleanup INT TERM EXIT
  log "前后端已启动。输入命令管理，q 或 Ctrl+C 退出并停止服务："
  while true; do
    echo "  [1] 重启后端  [2] 重启前端  [3] 重启前后端  [4] 状态  [5] 看日志  [q] 退出"
    printf "[dev] > "
    if ! read -r cmd; then echo; warn "会话结束，停止服务 ..."; break; fi
    case "$cmd" in
      1) restart_backend ;;
      2) restart_frontend ;;
      3) restart_backend; restart_frontend ;;
      4) status ;;
      5) show_logs ;;
      q|Q) log "退出，停止服务 ..."; break ;;
      "") ;;
      *) warn "未知命令：$cmd" ;;
    esac
  done
}

# 状态码翻译成中文
code_to_text() {
  local code=$1
  case "$code" in
    ""|000) echo "未启动（端口无响应）" ;;
    200)    echo "运行中（健康）" ;;
    3*)     echo "运行中（HTTP $code 重定向）" ;;
    4*|5*)  echo "运行中但异常（HTTP $code）" ;;
    *)      echo "未知状态（HTTP $code）" ;;
  esac
}

status() {
  local b f
  b=$(probe "$BPORT" /api/health localhost); f=$(probe "$FPORT" / localhost)
  devlog "status 后端=$b 前端=$f"
  log "后端  : http://localhost:$BPORT/api/health -> $(code_to_text "$b")"
  log "前端  : http://localhost:$FPORT/         -> $(code_to_text "$f")"
  if [ "$b" = "200" ] && [ "$f" = "200" ]; then
    log "结论  : 前后端都在正常运行"
  else
    local not=""
    [ "$b" != "200" ] && not="后端"
    [ "$f" != "200" ] && not="${not:+$not+}前端"
    warn "结论  : ${not} 未就绪（刚重启可能仍在启动，稍等再查；或看 .devlogs 日志）"
  fi
}

# 等前后端就绪后再继续（初始启动用，避免服务还没起来就打印「未就绪」状态）
wait_services_ready() {
  local i ok code
  devlog "wait 后端 /api/health 开始（上限 90s）"
  ok=0
  for i in $(seq 1 90); do
    code=$(probe "$BPORT" /api/health localhost)
    [ "$code" = "200" ] && { ok=1; break; }
    sleep 1
    [ $((i % 5)) -eq 0 ] && log "  仍在等待后端，已 ${i}s（每秒探活 /api/health，就绪即继续，上限 90s）"
  done
  if [ "$ok" = "1" ]; then
    devlog "wait 后端 就绪（${i}s）"; log "后端已就绪"
  else
    devlog "wait 后端 90s 超时未就绪"; warn "后端 90s 内未就绪，看 $LOG_DIR/backend.err.log"
  fi
  devlog "wait 前端 / 开始（上限 20s）"
  ok=0
  for i in $(seq 1 20); do
    code=$(probe "$FPORT" / localhost)
    [ "$code" = "200" ] && { ok=1; break; }
    sleep 1
    [ $((i % 5)) -eq 0 ] && log "  仍在等待前端，已 ${i}s（每秒探活，就绪即继续，上限 20s）"
  done
  if [ "$ok" = "1" ]; then
    devlog "wait 前端 就绪（${i}s）"; log "前端已就绪"
  else
    devlog "wait 前端 20s 超时未就绪"; warn "前端 20s 内未就绪，看 $LOG_DIR/frontend.log"
  fi
}

# 仅重启后端并探活（改后端 .py 后用，对齐 dev.ps1 的 backend 模式）
# 一次性命令：后端以 nohup 脱离式独立运行，脚本退出后后端继续存活（不进前台托管）
restart_backend_only() {
  if port_listening "$BPORT"; then
    warn "$BPORT 已被占用，重启中 ..."
    kill_port "$BPORT"
    wait_port_free "$BPORT" || warn "$BPORT 仍被占用，后端可能启动失败"
  fi
  check_venv
  log "启动后端 (: $BPORT)"
  ( cd "$BACKEND" && nohup "$VENV_PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$BPORT" \
      > "$LOG_DIR/backend.log" 2> "$LOG_DIR/backend.err.log" & echo $! > "$LOG_DIR/backend.pid" )
  log "等待 /api/health 就绪 ..."
  local ok=0 i code
  for i in $(seq 1 90); do
    sleep 1
    code=$(probe "$BPORT" /api/health localhost)
    if [ "$code" = "200" ]; then ok=1; break; fi
    [ $((i % 5)) -eq 0 ] && log "  仍在等待，已 ${i}s（每秒探活一次，就绪即继续）"
  done
  if [ "$ok" = "1" ]; then
    log "后端运行正常（/api/health=200）。新代码改动已生效。"
  else
    err "90s 内 /api/health 未返回 200，请检查日志：$LOG_DIR/backend.log 与 backend.err.log"
    exit 1
  fi
}

case "${1:-start}" in
  start)
    start_deps
    ensure_backend
    ensure_frontend
    wait_services_ready
    status
    run_foreground
    ;;
  restart)
    start_deps
    kill_port "$BPORT"
    kill_port "$FPORT"
    wait_port_free "$BPORT" || true
    wait_port_free "$FPORT" || true
    launch_backend
    launch_frontend
    wait_services_ready
    status
    run_foreground
    ;;
  stop)
    stop_all
    ;;
  status)
    status
    ;;
  backend)
    restart_backend_only
    ;;
  *)
    echo "用法: $0 {start|restart|stop|status|backend}"
    exit 1
    ;;
esac
