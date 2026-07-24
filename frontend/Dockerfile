# ---------- 构建阶段 ----------
FROM node:22-alpine AS build
WORKDIR /app

# 优先用 lock 文件做确定性安装
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---------- 运行阶段 ----------
FROM nginx:alpine
# 用项目自带的前端 SPA 配置（含 history 路由 fallback + gzip）
COPY deploy/nginx/frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD wget -q -O /dev/null http://localhost/ || exit 1
