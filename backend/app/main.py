from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import ask, health, knowledge, trending


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ponytail: embedding API 客户端即时创建, 无需预加载
    yield


app = FastAPI(title="知海 Knoa API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(trending.router, prefix="/api")
app.include_router(ask.router, prefix="/api")
