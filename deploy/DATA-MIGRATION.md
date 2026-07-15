# Knoa 数据迁移（新服务器必读）

> 头号坑：知识库 md 种子文件**不进 git**（已 gitignore），系统的唯一真相在
> **老服务器 Postgres** 里。你 `git clone` 到新机器是**空库**——登录后
> 知识库列表空、问答无来源。必须在启动后先做数据迁移，二选一。

## 方案 A：直接迁 Postgres（推荐，保真）

老服务器上已经有每日 `pg_dump` 备份（compose 的 `backup` 服务，落 `knoa_backups` 卷）。
把最新的 `.sql.gz` 拷到新服务器，恢复即可，**连用户账号/记忆/图谱一起带走**：

```bash
# 1) 新服务器：先起 postgres（别起 backend，避免空库被占用）
docker compose up -d postgres redis

# 2) 把老服务器的备份拷过来（示例用 scp，任意方式都行）
scp user@OLD_SERVER:/var/lib/docker/volumes/knoa_backups/_data/knoa_2026xxxx.sql.gz ./knoa_dump.sql.gz

# 3) 恢复（gzip 流式解压 | psql，--no-owner 忽略原角色）
gunzip -c knoa_dump.sql.gz | docker compose exec -T postgres \
  psql -U knoa -d knoa --no-owner
```

恢复完再 `docker compose up -d backend frontend edge` 即可，KB / 文档 / 用户 / 记忆全在。

## 方案 B：重新 ingest 种子（仅当你只要种子文档）

适合老库已脏、想重来的情况：

```bash
# 1) 把老机器上被 gitignore 的 md 种子文件拷到新机器 backend/app/data/markdown/
scp -r user@OLD_SERVER:/path/to/knoa/backend/app/data/markdown/ ./backend/app/data/markdown/

# 2) 起全栈后，调用摄入接口重建（走真实 DashScope embedding，重新算 1024 维）
#    ingest_seed 会从磁盘 md 重建 pgvector(JSONB) 数据
docker compose exec backend uv run python -m app.scripts.ingest_seed
```

> 注意：方案 B **只恢复种子文档**，老库里用户上传的文档 / 账号 / 长期记忆都丢了。
> 一般优先方案 A。

## 验证

```bash
curl -kI https://<你的域名>/api/health      # 200
# 登录后看知识库列表非空、随便问一个种子里的问题能有来源
docker compose exec postgres psql -U knoa -d knoa -c "SELECT count(*) FROM doc_chunk;"
# 应 > 0
```

## 后续备份

`backup` 服务已在跑（每日 `pg_dump` → `knoa_backups` 卷，保留 7 天）。
**务必把 `knoa_backups` 卷也定期拷到另一台机器 / 对象存储**——卷本身只在本机，
服务器没了备份也没了。
