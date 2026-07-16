"""结构化日志配置，零依赖（仅标准库）。

- 统一格式：时间 级别 模块 [rid=xxx] 消息
- 通过 contextvars 注入 request_id，使一次请求的全链路日志可串联
- setup_logging() 幂等，可在 app 导入期安全调用（含 pytest 用 ASGITransport 不触发 lifespan 的场景）
"""
import contextvars
import logging
import sys

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
    if level is None:
        try:
            from app.config import settings
            level = settings.LOG_LEVEL or "INFO"
        except Exception:
            level = "INFO"
    # pytest 自己管 logging handler，test 环境下不抢（force=False），
    # 仅复用已有配置；非 test 才 force 接管单一 root handler。
    force = True
    try:
        from app.config import settings as _s
        if getattr(_s, "APP_ENV", "") == "test":
            force = False
    except Exception:
        pass
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s [rid=%(request_id)s] %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(_RequestIdFilter())
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[handler],
        force=force,
    )
    # 降噪：框架访问日志保持 WARNING 以上，避免压测时刷屏
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    _CONFIGURED = True
