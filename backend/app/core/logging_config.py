"""结构化日志配置，零依赖（仅标准库）。

- 统一格式：时间 级别 模块 [rid=xxx] 消息
- 通过 contextvars 注入 request_id，使一次请求的全链路日志可串联
- setup_logging() 幂等，可在 app 导入期安全调用（含 pytest 用 ASGITransport 不触发 lifespan 的场景）
"""
import contextvars
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 每个请求一个 id，由 observability middleware 写入；日志 filter 自动读取
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_CONFIGURED = False


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # 允许调用方用 extra={"request_id": ...} 显式覆盖（sse-starlette 子任务里
        # contextvars 可能不传播，ask 路由改为显式传 rid）
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


def setup_logging(level: str | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    is_test = False
    log_dir = ""
    try:
        from app.config import settings
        level = level or settings.LOG_LEVEL or "INFO"
        log_dir = getattr(settings, "LOG_DIR", "") or ""
        is_test = getattr(settings, "APP_ENV", "") == "test"
    except Exception:  # noqa: BLE001  (intentional catch-all: best-effort defaults if settings unavailable)
        level = level or "INFO"
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s [rid=%(request_id)s] %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(fmt)
    stdout_handler.addFilter(_RequestIdFilter())
    handlers: list[logging.Handler] = [stdout_handler]
    # 落盘（test 环境跳过，避免污染 pytest 的 logging 接管）：
    # app.log 全量便于按 rid 串联一次请求全链路；error.log 仅 ERROR+（含未捕获异常
    # traceback），出问题先翻它。轮转防无限增长。任何落盘失败都降级回纯 stdout，
    # 绝不让日志把服务拖崩。
    if log_dir and not is_test:
        try:
            base = Path(log_dir)
            if not base.is_absolute():
                # 相对路径锚定 backend/（config.py 所在目录的上一级），不随启动 cwd 漂移
                base = Path(__file__).resolve().parents[2] / base
            base.mkdir(parents=True, exist_ok=True)
            app_fh = RotatingFileHandler(
                base / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            app_fh.setFormatter(fmt)
            app_fh.addFilter(_RequestIdFilter())
            err_fh = RotatingFileHandler(
                base / "error.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            err_fh.setLevel(logging.ERROR)
            err_fh.setFormatter(fmt)
            err_fh.addFilter(_RequestIdFilter())
            handlers += [app_fh, err_fh]
        except Exception:  # noqa: BLE001  (intentional catch-all: 落盘失败降级纯 stdout，不阻断启动)
            handlers = [stdout_handler]
    # pytest 自己管 logging handler，test 环境下不抢（force=False），
    # 仅复用已有配置；非 test 才 force 接管 root handler。
    force = not is_test
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=handlers,
        force=force,
    )
    # 降噪：框架访问日志保持 WARNING 以上，避免压测时刷屏
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    _CONFIGURED = True
