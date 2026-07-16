"""进程内指标累加器，零依赖（仅标准库）。

提供：活跃请求数、按归一化端点拆解的请求数 / 延迟样本（P50/P95/P99）
/ 错误数 / 状态码分布，以及全局累计与错误率。snapshot() 供 /api/metrics 返回。

设计取舍（ponytail: 单机单进程够用，多 worker 不聚合；要历史趋势再上 Prometheus）：
- 延迟样本用定长 deque(maxlen=5000) 做近似分位，避免无限增长
- 全局一把 threading.Lock 保护聚合状态；压测量级下足够，瓶颈在 IO 不在锁
"""
import re
import threading
import time
from collections import deque

_LOCK = threading.Lock()
_STARTED_AT = time.time()
_ACTIVE = 0
_TOTAL = 0
_ERRORS = 0
_SLOW = 0
_SLOW_THRESHOLD = 1.0  # 秒；慢请求阈值，固定即可，配置化若确需再加
_SAMPLES_MAX = 5000
_ENDPOINTS: dict[str, dict] = {}

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_NUM_RE = re.compile(r"(?<=/)\d+(?=/|$)")


def normalize_path(path: str) -> str:
    """把路径中的 UUID / 数字段归一为 {id}，避免每资源一个 key 爆炸。"""
    return _NUM_RE.sub("{id}", _UUID_RE.sub("{id}", path))


def get_slow_threshold() -> float:
    return _SLOW_THRESHOLD


def inc_active() -> None:
    global _ACTIVE
    with _LOCK:
        _ACTIVE += 1


def dec_active() -> None:
    global _ACTIVE
    with _LOCK:
        _ACTIVE = max(0, _ACTIVE - 1)


def record(endpoint: str, latency: float, status_code: int, is_error: bool) -> None:
    global _TOTAL, _ERRORS, _SLOW
    with _LOCK:
        _TOTAL += 1
        if is_error:
            _ERRORS += 1
        if latency >= _SLOW_THRESHOLD:
            _SLOW += 1
        ep = _ENDPOINTS.get(endpoint)
        if ep is None:
            ep = {
                "count": 0,
                "errors": 0,
                "statuses": {},
                "latencies": deque(maxlen=_SAMPLES_MAX),
            }
            _ENDPOINTS[endpoint] = ep
        ep["count"] += 1
        if is_error:
            ep["errors"] += 1
        ep["statuses"][status_code] = ep["statuses"].get(status_code, 0) + 1
        ep["latencies"].append(latency)


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def snapshot() -> dict:
    with _LOCK:
        endpoints = {}
        for name, ep in sorted(_ENDPOINTS.items()):
            lats = sorted(ep["latencies"])
            endpoints[name] = {
                "count": ep["count"],
                "errors": ep["errors"],
                "error_rate": round(ep["errors"] / ep["count"], 4) if ep["count"] else 0.0,
                "p50_ms": round(_percentile(lats, 0.50) * 1000, 1),
                "p95_ms": round(_percentile(lats, 0.95) * 1000, 1),
                "p99_ms": round(_percentile(lats, 0.99) * 1000, 1),
                "statuses": dict(ep["statuses"]),
            }
        return {
            "uptime_seconds": round(time.time() - _STARTED_AT, 1),
            "active_requests": _ACTIVE,
            "total_requests": _TOTAL,
            "total_errors": _ERRORS,
            "global_error_rate": round(_ERRORS / _TOTAL, 4) if _TOTAL else 0.0,
            "slow_requests": _SLOW,
            "slow_threshold_seconds": _SLOW_THRESHOLD,
            "endpoints": endpoints,
        }
