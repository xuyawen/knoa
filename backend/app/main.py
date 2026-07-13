import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.db import User
from app.routers import (
    ask,
    auth,
    feedback,
    health,
    knowledge,
    sessions,
    sources,
    trending,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ponytail: embedding API 客户端即时创建, 无需预加载
    # 确保所有模型表已创建（幂等，已存在的表不受影响）
    from app.database import init_db
    await init_db()
    # Phase 2: 首次启动且无任何用户时，自动创建初始管理员（幂等）
    async with AsyncSessionLocal() as session:
        exists = await session.scalar(select(User).limit(1))
        if exists is None:
            admin = User(
                id=uuid.uuid4(),
                username=settings.ADMIN_USERNAME,
                password_hash=User.hash_password(settings.ADMIN_PASSWORD),
                display_name=settings.ADMIN_DISPLAY_NAME,
                role="admin",
            )
            session.add(admin)
            await session.commit()
            print(
                f"[bootstrap] 已创建初始管理员账号: {settings.ADMIN_USERNAME} "
                f"(请尽快在 .env 修改 ADMIN_PASSWORD)",
                flush=True,
            )
    yield


app = FastAPI(title="知海 Knoa API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(trending.router, prefix="/api")
app.include_router(ask.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
