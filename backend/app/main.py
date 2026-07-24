import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update

from app.config import settings, validate_production_settings
from app.core.logging_config import request_id_var, setup_logging
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
from app.db import ChatSession, Role, User
from app.routers import (
    analytics,
    announcements,
    ask,
    auth,
    departments,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 生产环境配置强校验（弱密钥/弱口令/维度错配 → 直接启动失败，fail-fast）
    validate_production_settings()
    # ponytail: embedding API 客户端即时创建, 无需预加载
    # 确保所有模型表已创建（幂等，已存在的表不受影响）
    from app.database import init_db
    await init_db()
    # Phase 2: 首次启动且无任何用户时，自动创建初始管理员（幂等）
    async with AsyncSessionLocal() as session:
        # 内置 admin 角色 id（_seed_roles 已保证存在）
        admin_role = await session.scalar(select(Role).where(Role.key == "admin"))
        admin_role_id = admin_role.id if admin_role else None
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
                department=settings.ADMIN_DEPARTMENT,
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
            if admin.department is None:
                admin.department = settings.ADMIN_DEPARTMENT
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
        return response
    except Exception:
        logger.exception("unhandled %s %s", request.method, request.url.path)
        raise
    finally:
        elapsed = time.perf_counter() - start
        dec_active()
        record(normalize_path(request.url.path), elapsed, status, status >= 500)
        request_id_var.reset(ctx)
        if elapsed >= get_slow_threshold():
            logger.warning(
                "slow %0.2fs %s %s -> %d",
                elapsed, request.method, request.url.path, status,
            )


app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
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
app.include_router(tasks.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(operations.router, prefix="/api")
app.include_router(announcements.router, prefix="/api")
app.include_router(roles.router, prefix="/api")
app.include_router(oss.router, prefix="/api")
