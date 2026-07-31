import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

# LangSmith 追踪开关必须显式注入 os.environ。
# pydantic BaseSettings(env_file=".env") 只把 .env 的值填进 settings 对象，
# 不会写 os.environ；而 langsmith SDK 仅靠 os.environ 读取 LANGSMITH_TRACING。
# 不先 load_dotenv()，tracing 实际永不开启，后台收不到任何 trace。
# 放在所有 app.* 导入之前，确保 langsmith 在任意 @traceable 被 import 前
# 就能读到开关。
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update

from app.config import settings, validate_production_settings

# 兜底：即便启动目录异常导致上面的 load_dotenv 未命中 .env，也把 settings 中
# 已确认的 LangSmith 配置显式写入 os.environ（langsmith 只读 os.environ）。
for _ls_key in ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT", "LANGSMITH_ENDPOINT"):
    _ls_val = getattr(settings, _ls_key, "")
    if _ls_val and not os.environ.get(_ls_key):
        os.environ[_ls_key] = str(_ls_val)
from app.core.logging_config import request_id_var, setup_logging
from app.models.errors import capture_error
from app.core.metrics import (
    dec_active,
    get_slow_threshold,
    inc_active,
    normalize_path,
    record,
)
from app.core.security import (
    create_access_token,
    decode_access_token,
    extract_token,
    is_token_revoked,
)
from app.database import AsyncSessionLocal
from app.deps import get_es
from app.db import ChatSession, Department, Role, User
from app.routers import (
    analytics,
    announcements,
    ask,
    auth,
    departments,
    errors,
    events,
    feedback,
    oss,
    graph,
    health,
    knowledge,
    memory,
    metrics,
    operations,
    roles,
    sessions,
    sources,
    tasks,
    trending,
    settings as settings_router,
    tts as tts_router,
)


async def _rollup_trending():
    """将昨日 Redis 热搜计数落盘到 Trending 表。

    幂等：若 DB 已存在昨日记录则跳过（重启不重复写入）。
    best-effort：Redis 不可用 / 无数据时静默返回，不阻塞启动。
    """
    from datetime import datetime, timedelta, timezone

    from redis.exceptions import RedisError

    from app.db import Trending
    from app.deps import get_redis

    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    try:
        counts = await get_redis().get_day_counts(yesterday)
    except RedisError:
        return
    if not counts:
        return
    async with AsyncSessionLocal() as session:
        exists = await session.scalar(
            select(Trending.id).where(Trending.date == yesterday).limit(1)
        )
        if exists:
            return
        for q, c in counts:
            session.add(Trending(question=q, count=c, date=yesterday))
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 生产环境配置强校验（弱密钥/弱口令/维度错配 → 直接启动失败，fail-fast）
    validate_production_settings()
    # ponytail: embedding API 客户端即时创建, 无需预加载
    # 确保所有模型表已创建（幂等，已存在的表不受影响）
    from app.database import init_db
    await init_db()
    # 热搜落盘：将昨日 Redis 计数写入 Trending 表（幂等），
    # 保证 Redis 重启 / key 过期后榜单仍有历史数据可查。
    await _rollup_trending()
    # Phase 2: 首次启动且无任何用户时，自动创建初始管理员（幂等）
    async with AsyncSessionLocal() as session:
        # 内置 admin 角色 id（_seed_roles 已保证存在）
        admin_role = await session.scalar(select(Role).where(Role.key == "admin"))
        admin_role_id = admin_role.id if admin_role else None
        # admin 部门：按名解析 department_id（部门表已播种；解析不到留 NULL，admin 为超管不依赖部门权限）
        admin_dept_id = None
        if settings.ADMIN_DEPARTMENT:
            admin_dept = await session.scalar(
                select(Department).where(Department.name == settings.ADMIN_DEPARTMENT)
            )
            admin_dept_id = admin_dept.id if admin_dept else None
        admin = await session.scalar(
            select(User).where(User.username == settings.ADMIN_USERNAME)
        )
        if admin is None:
            admin = await session.scalar(select(User).order_by(User.created_at).limit(1))
        if admin is None:
            admin = User(
                id=uuid.uuid4(),
                username=settings.ADMIN_USERNAME,
                password_hash=User.hash_password(settings.ADMIN_PASSWORD),
                display_name=settings.ADMIN_DISPLAY_NAME,
                role_id=admin_role_id,
                email=settings.ADMIN_EMAIL,
                department_id=admin_dept_id,
                employee_id=settings.ADMIN_EMPLOYEE_ID,
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)
        else:
            # ponytail: 补全 admin 空缺档案字段，幂等仅填空缺项
            changed = False
            if admin.email is None:
                admin.email = settings.ADMIN_EMAIL
                changed = True
            if admin.department_id is None and admin_dept_id is not None:
                admin.department_id = admin_dept_id
                changed = True
            if admin.employee_id is None:
                admin.employee_id = settings.ADMIN_EMPLOYEE_ID
                changed = True
            if changed:
                await session.commit()
        # 迁移遗留会话：user_id 为 NULL 的会话归属到该管理员，
        # 避免上线会话隔离后旧会话对所有用户不可见（幂等，仅影响 NULL 行）。
        await session.execute(
            update(ChatSession)
            .where(ChatSession.user_id.is_(None))
            .values(user_id=str(admin.id))
        )
        await session.commit()
    yield

    # 统一关闭 ES 单例（httpx 连接池），避免连接泄漏（P1-1）
    try:
        await get_es().aclose()
    except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, ignore ES close errors during shutdown)
        pass
    # 统一关闭 Redis 连接（main 启动期创建单例，此前未关闭 → 连接泄漏）
    try:
        from app.deps import get_redis

        await get_redis().close()
    except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, ignore redis close errors during shutdown)
        pass
    # 统一关闭对象存储连接（S3 模式 httpx 连接池此前未关闭 → 泄漏）
    try:
        from app.core.storage import get_object_store

        store = get_object_store()
        if hasattr(store, "aclose"):
            await store.aclose()
    except Exception:  # noqa: BLE001  (intentional catch-all: best-effort, ignore object-store close errors during shutdown)
        pass


# ponytail: 生产环境关闭 API 文档与 OpenAPI schema，避免向匿名暴露完整攻击面
_docs_disabled = settings.APP_ENV == "production"
app = FastAPI(
    title="知海 Knoa API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _docs_disabled else "/docs",
    redoc_url=None if _docs_disabled else "/redoc",
    openapi_url=None if _docs_disabled else "/openapi.json",
)
setup_logging()
logger = logging.getLogger("knoa")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
)

# 滑动过期中间件：携带有效令牌的认证请求，在剩余有效期低于总寿命
# 的 30% 时，才重新签发一个全新 24h 有效期的令牌，并通过
# X-Access-Token 响应头下发。
# 效果：活跃使用期间令牌保持稳定（不每次都换），只有快过期时
# （如第 23 小时那次请求，剩 ~4% < 30%）才重置回完整 24h；
# 闲置超过 24h 仍会失效。兼顾滑动效果与减少 token churn。
SLIDING_TOKEN_HEADER = "X-Access-Token"
# 剩余有效期低于总寿命的比例阈值时才重签（0.30 = 30%）
SLIDING_REFRESH_RATIO = 0.30


@app.middleware("http")
async def sliding_session(request: Request, call_next):
    raw = extract_token(request)
    new_token: str | None = None
    if raw:
        try:
            payload = decode_access_token(raw)
            total = settings.JWT_EXPIRE_MINUTES * 60
            remaining = payload["exp"] - int(time.time())
            # 仅当剩余有效期不足总寿命的 30% 时才重签，
            # 避免每次请求都换新 token（token churn + 多标签页竞态）。
            if remaining < total * SLIDING_REFRESH_RATIO:
                # ponytail: 重签前必须校验吊销黑名单，否则 logout 后临近过期的
                # 旧 token 仍可换发全新未吊销 token，使 logout 实质失效
                if await is_token_revoked(payload.get("jti", "")):
                    new_token = None
                else:
                    new_token = create_access_token(
                        payload["sub"], payload["username"], payload["role"]
                    )
        except Exception:  # noqa: BLE001  (intentional catch-all: don't reissue token on decode failure, route handles 401)
            # 令牌无效/已过期：不重新签发，交由路由自身按原逻辑 401。
            new_token = None
    response = await call_next(request)
    if new_token:
        response.headers[SLIDING_TOKEN_HEADER] = new_token
        # 同步刷新 HttpOnly Cookie（滑动令牌，前端 JS 读不到）
        response.set_cookie(
            key=settings.COOKIE_NAME,
            value=new_token,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            max_age=settings.JWT_EXPIRE_MINUTES * 60,
            path="/",
        )
    return response


async def _extract_error_detail(response) -> tuple[str | None, Response]:
    """读出错误响应体里的 detail（FastAPI 统一错误结构 {"detail": ...}）。

    BaseHTTPMiddleware 的 call_next 返回 StreamingResponse，body_iterator 只能消费
    一次；这里消费后用原状态码/头/媒体类型重建一个 Response 返回，客户端无感知。
    解析失败（非 JSON / 无 detail）也要重建响应，detail 返回 None。消息截断防超长。
    """
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
    body = b"".join(chunks)
    detail: str | None = None
    try:
        payload = json.loads(body)
        raw = payload.get("detail") if isinstance(payload, dict) else None
        if isinstance(raw, str):
            detail = raw
        elif raw is not None:
            detail = json.dumps(raw, ensure_ascii=False)
    except (ValueError, UnicodeDecodeError):
        detail = None
    if detail and len(detail) > 500:
        detail = detail[:500] + "…"
    # content-length/content-type 由 Response 按 body+media_type 重算，避免与旧头冲突
    headers = {
        k: v for k, v in response.headers.items()
        if k.lower() not in ("content-length", "content-type")
    }
    rebuilt = Response(
        content=body,
        status_code=response.status_code,
        headers=headers,
        media_type=response.media_type,
    )
    return detail, rebuilt


@app.middleware("http")
async def observability(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    request.state.request_id = rid
    ctx = request_id_var.set(rid)
    start = time.perf_counter()
    inc_active()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        # 4xx/5xx 读出响应体里的 detail，供错误管理页展示「具体报错」（重建响应，
        # 客户端拿到的 body/状态码不变）。只读错误响应，200/SSE 流式响应不受影响。
        if status >= 400:
            err_detail, response = await _extract_error_detail(response)
            if err_detail:
                request.state.error_detail = err_detail
        # 回传 rid：前端上报错误时携带它，可与后端日志按 rid 精确串联同一次请求
        response.headers["X-Request-ID"] = rid
        return response
    except Exception:
        logger.exception("unhandled %s %s", request.method, request.url.path)
        raise
    finally:
        elapsed = time.perf_counter() - start
        dec_active()
        record(normalize_path(request.url.path), elapsed, status, status >= 500)
        request_id_var.reset(ctx)
        path = request.url.path
        # 业务错误落日志：此前只有未捕获异常(5xx)有 traceback，4xx（参数错/越权/
        # 限流/校验失败）完全静默，查「为什么被拒」无据可查。现 4xx/5xx 都记一行
        # （rid+method+path+状态码+耗时）。跳过 /api/auth/me 与 /api/events 的 401：
        # 前者是未登录页加载的正常探测、后者是上报端点的匿名请求，均属预期噪声。
        if status >= 400 and not (
            status == 401 and (path.startswith("/api/auth/me") or path.startswith("/api/events"))
        ):
            logger.log(
                logging.ERROR if status >= 500 else logging.WARNING,
                "http %d %s %s (%.2fs)", status, request.method, path, elapsed,
            )
            # 同步落库错误管理页（fire-and-forget）：与日志互补——日志要上机翻，
            # 这里可在页面上按来源/状态码/路径浏览检索。跳过 /api/events 自身，避免上报递归。
            if not path.startswith("/api/events"):
                capture_error(
                    source="backend",
                    level="error" if status >= 500 else "warn",
                    method=request.method,
                    path=path,
                    status_code=status,
                    rid=rid,
                    message=getattr(request.state, "error_detail", None),
                    ip=(request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
                    or (request.client.host if request.client else None),
                )
        if elapsed >= get_slow_threshold():
            logger.warning(
                "slow %0.2fs %s %s -> %d",
                elapsed, request.method, path, status,
            )


app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
# tasks 路由须先于 knowledge 注册：/api/documents/tasks 是静态路由，
# 若晚于 /api/documents/{doc_id}（动态）注册会被其抢匹配，导致 tasks 被当 UUID → 500
app.include_router(tasks.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(trending.router, prefix="/api")
app.include_router(ask.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(tts_router.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(departments.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(operations.router, prefix="/api")
app.include_router(announcements.router, prefix="/api")
app.include_router(roles.router, prefix="/api")
app.include_router(errors.router, prefix="/api")
app.include_router(oss.router, prefix="/api")
