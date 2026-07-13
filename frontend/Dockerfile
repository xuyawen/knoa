# Knoa frontend — 多阶段构建（node 构建 → nginx 静态托管）
# node:22 对齐开发用 Node 22.22.2
FROM node:22-slim AS build

WORKDIR /app

# 依赖层缓存（npm ci 需要 package-lock.json，已在仓库中）
COPY package.json package-lock.json ./
RUN npm ci

# 复制源码并构建（vue-tsc 类型检查 + vite build）
COPY . .
RUN npm run build

# ---- 运行阶段 ----
FROM nginx:alpine

# 用自定义配置覆盖默认：反代 /api 到 backend，并关闭 SSE 缓冲
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# nginx:alpine 自带前台启动入口，无需自定义 CMD
