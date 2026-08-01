# ---------- 构建阶段 ----------
FROM node:22-alpine AS build
WORKDIR /app

# 国内 npm 源，避免 registry.npmjs.org 出网受限（构建失败）
ENV npm_config_registry=https://registry.npmmirror.com

# 优先用 lock 文件做确定性安装
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# 演示账号自动填充：生产构建若没有 .env，则使用示例文件生成（Vite 只认 .env）
RUN if [ ! -f .env ]; then cp .env.example .env; fi

RUN npm run build

# ---------- 运行阶段 ----------
FROM nginx:alpine
# 用项目自带的前端 SPA 配置（含 history 路由 fallback + gzip）
COPY deploy/nginx/frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD wget -q -O /dev/null http://localhost/ || exit 1
