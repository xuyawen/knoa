# Knoa backend — python:3.12-slim（numpy 2.5.1 要求 >=3.12，与 pyproject requires-python 对齐）
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/ \
    UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple/

WORKDIR /app

# apt 源换国内镜像（deb.debian.org 在国内 403）；openssl 供 entrypoint 生成自签证书，curl 供健康检查
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g; s|https://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends openssl curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（按 uv.lock 可复现地装依赖）；走清华源避免 pypi.org 出网受限
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple/ uv

# 先只复制依赖声明，最大化利用缓存层
COPY pyproject.toml uv.lock ./
RUN uv sync --no-install-project --index-url https://pypi.tuna.tsinghua.edu.cn/simple/

# 复制应用代码（.dockerignore 已排除 .env / certs / .venv 等）
COPY . .

# 同步项目本身（安装进 .venv）；不加 --frozen 以便重新解析走国内源
RUN uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple/

# 上传目录需可写（compose 挂载同名卷，777 仅兜底，生产应改属主）
RUN mkdir -p app/data/uploads && chmod 777 app/data/uploads

EXPOSE 8000

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# 以非 root 用户运行（降低容器被攻破后的影响面；uvicorn 绑 8000 无需特权端口）
RUN groupadd --system appgroup \
    && useradd --system --gid appgroup appuser \
    && chown -R appuser:appgroup /app

# uv 缓存目录重定向到 appuser 可写路径（默认 HOME=/home/appuser 无写权会启动失败）
# 必须在创建 appuser/appgroup 之后执行 chown，否则报 invalid user
RUN mkdir -p /app/.uv-cache && chown appuser:appgroup /app/.uv-cache
ENV UV_CACHE_DIR=/app/.uv-cache

USER appuser

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
