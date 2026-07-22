"""pytest 全局配置：

- 在任何 app 导入前设置测试环境变量（指向独立测试库 knoa_pytest）。
- session 级 fixture：在 host Postgres 上建/清测试库，
  并用「与生产一致的 Alembic 迁移」建表（同时顺带验证迁移本身可用）。
- 用测试替身替换 HTTP 层依赖（LLM / Embedder / Redis / Graph），
  使整条 API + 问答链路在无 API key 时也能端到端跑通。

测试库连接信息可经环境变量覆盖：
- 容器内跑（compose 服务名）：KNOA_TEST_PG_HOST=postgres KNOA_TEST_PG_PORT=5432
- 宿主机跑（端口映射）：默认 localhost:5433
"""

import os

# ── 测试库连接信息（容器内用 compose 服务名覆盖）──
PG_HOST = os.environ.get("KNOA_TEST_PG_HOST", "localhost")
PG_PORT = os.environ.get("KNOA_TEST_PG_PORT", "5433")
REDIS_HOST = os.environ.get("KNOA_TEST_REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("KNOA_TEST_REDIS_PORT", "6380")
TEST_DB = "knoa_pytest"
BASE_DB = "knoa"
PG_USER = "knoa"
PG_PASS = "knoa"

# ── 必须在本文件 import app 之前设置 ──
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = (
    f"postgresql+asyncpg://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{TEST_DB}"
)
os.environ["REDIS_URL"] = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
os.environ["GRAPH_ENABLED"] = "False"  # 关闭图谱抽取，避免测试时调 LLM
os.environ["MEMORY_ENABLED"] = "False"  # 关闭长期记忆后台抽取
os.environ["JWT_SECRET"] = "test-secret-change-me"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["ADMIN_DISPLAY_NAME"] = "测试管理员"
os.environ["CORS_ORIGINS"] = "http://localhost:8080"
os.environ["LOG_LEVEL"] = "WARNING"

import asyncpg  # noqa: E402
import uuid  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

import app.database as db_mod  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import _run_alembic_upgrade  # noqa: E402
from app.db import User  # noqa: E402
from tests._fakes import FakeEmbedder, FakeLLM, FakeRedis  # noqa: E402

# ── 用默认 QueuePool 重建一个指向测试库的引擎，替换 app.database 的
# engine 与 AsyncSessionLocal。顺序必须在 import 任何 app 子模块之前完成
# （它们会 `from app.database import AsyncSessionLocal` 在各自命名空间绑定名字）。
#
# 跨事件循环问题靠「整个测试会话共用一个 loop」解决（见 pyproject 的
# asyncio_default_fixture_loop_scope=session）：asyncpg 连接绑定创建它的 loop，
# 单 loop 下所有连接始终合法，QueuePool 可安全复用。
#
# 同一请求内「多表写入需落同一连接（外键可见）」的问题，由
# app.deps.get_db 的「请求级单会话」模式从根上保证，与本文件无关。
_app_engine = create_async_engine(os.environ["DATABASE_URL"], echo=False, future=True)
db_mod.engine = _app_engine
db_mod.AsyncSessionLocal = async_sessionmaker(
    _app_engine, class_=AsyncSession, expire_on_commit=False
)

# ── 用 FastAPI 的 dependency_overrides 把 HTTP 层依赖换成测试替身 ──
# 关键坑：路由里 `Depends(get_embedder)` 在「路由定义时」就捕获了
# app.deps.get_embedder 这个**对象引用**；之后单纯重绑
# `ask_mod.get_embedder = lambda ...`（模块属性）**不会**改变已捕获的对象，
# 替身不生效 —— 这正是之前测试打到真实 LLM / Embedding API 的根因
# （容器里的 .env 带了真实 key，真实 embedding 返回 1024 维，而测试
# 摄入用的是 FakeEmbedder 的 1536 维，矩阵乘法维数不符而报错）。
#
# FastAPI 的 dependency_overrides 按「依赖可调用对象的身份」在「请求时」
# 拦截，因此必须用它对 app.deps 里那三个函数打补丁，才能覆盖
# 所有路由（ask / knowledge 都 import 的是同一个 app.deps 函数对象）。
from app.deps import (  # noqa: E402
    get_embedder as _dep_get_embedder,
    get_llm as _dep_get_llm,
    get_redis as _dep_get_redis,
)
from app.main import app as _app  # noqa: E402  (app 实例在 app.main 顶层创建)

_app.dependency_overrides[_dep_get_embedder] = lambda: FakeEmbedder()
_app.dependency_overrides[_dep_get_llm] = lambda: FakeLLM()
_app.dependency_overrides[_dep_get_redis] = lambda: FakeRedis()


async def _drop_and_create():
    admin = await asyncpg.connect(
        user=PG_USER, password=PG_PASS, host=PG_HOST, port=int(PG_PORT), database=BASE_DB
    )
    await admin.execute(
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{TEST_DB}'"
    )
    await admin.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}"')
    await admin.execute(f'CREATE DATABASE "{TEST_DB}"')
    await admin.close()


async def _ensure_admin():
    """复刻 app.main.lifespan 里的初始管理员引导。

    测试用 ASGITransport 跑 app，不会触发 FastAPI 的 lifespan
    事件，因此这里手动建好初始 admin，否则登录接口无用户可验。
    幂等：已存在用户则跳过。
    """
    async with db_mod.AsyncSessionLocal() as s:
        exists = await s.scalar(select(User).limit(1))
        if exists is None:
            admin = User(
                id=uuid.uuid4(),
                username=settings.ADMIN_USERNAME,
                password_hash=User.hash_password(settings.ADMIN_PASSWORD),
                display_name=settings.ADMIN_DISPLAY_NAME,
                role="admin",
            )
            s.add(admin)
            await s.commit()


@pytest.fixture(scope="session", autouse=True)
async def prepare_test_db():
    await _drop_and_create()
    # 用与生产一致的 Alembic 迁移建表（验证迁移本身可用）
    await _run_alembic_upgrade()
    # lifespan 不触发，手动引导初始管理员（否则登录无用户）
    await _ensure_admin()
    # 清空连接池：_ensure_admin 在「session loop」开了一条 asyncpg
    # 连接并还回池中；pytest-asyncio 每个测试函数跑在各自的
    # function loop 上，若这条连接残留，下个测试复用它就会
    # 「attached to a different loop」。dispose 后池空，下个测试
    # 会在自己的 loop 上新建连接。
    await db_mod.engine.dispose()
    yield
    await _drop_and_create()


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def _dispose_engine_after_test():
    """每个测试后清空连接池：asyncpg 连接绑定创建它的事件循环，
    pytest-asyncio 每个测试一个 function loop，若不 dispose，上一个
    loop 的连接会被下一个测试复用而报 attached to a different loop。
    清空后每次都在当前测试的 loop 上新建连接。
    """
    yield
    await db_mod.engine.dispose()


@pytest_asyncio.fixture(loop_scope="function")
async def db_session():
    """测试直连用的 DB 会话：复用 conftest 打补丁的
    app.database.AsyncSessionLocal（指向测试库），且与 app 的 get_db
    都跑在「当前测试的 function loop」上（本 fixture 显式
    loop_scope="function"），因此两边 asyncpg 连接同 loop，
    数据互相可见，也不会出现跨 loop 报错。
    """
    async with db_mod.AsyncSessionLocal() as s:
        yield s
