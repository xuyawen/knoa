"""Knoa 后端压测脚本（Locust）。

覆盖四类端点，重点验证 SSE 流式 /api/ask 在并发下的稳定性：
- ask(sse)：POST /api/ask 流式消费，直到收到 event:done 或超时兜底
- knowledge-bases：GET（需鉴权）
- trending：GET（无需鉴权）
- health：GET 探活

运行（在 backend/ 下）：
    uv sync --extra load
    uv run --extra load locust -f loadtests/locustfile.py \
        --host https://localhost:8000 -u 50 -r 10 -t 1m

说明：
- 后端本地为自签 HTTPS，脚本默认 https + client.verify=False；
  若你关了 SSL 跑 http，把 host 改成 http:// 并删掉 on_start 里的
  `self.client.verify = False`。
- 登录用默认 admin/admin123（settings.ADMIN_USERNAME/PASSWORD），
  若 .env 改过，同步改下方 ADMIN_USER / ADMIN_PASS。
- 不传 -u/-r/-t 时 Locust 会打开 Web UI（默认 :8089）手动调速。
"""
import time

from locust import HttpUser, between, task

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# SSE 单次流式最长允许时间，超时即判定失败并释放 user（避免挂死占 concurrency）
SSE_TIMEOUT = 60.0


class KnoaUser(HttpUser):
    host = "https://localhost:8000"
    wait_time = between(0.5, 2.0)

    def on_start(self):
        # 自签证书，压测本地跳过校验
        self.client.verify = False
        with self.client.post(
            "/api/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
            name="login",
            catch_response=True,
        ) as r:
            if r.status_code == 200:
                self.token = r.json().get("access_token")
                r.success()
            else:
                r.failure(f"login {r.status_code}")
                self.token = None

    @task(3)
    def ask_sse(self):
        token = getattr(self, "token", None)
        if not token:
            return
        # 用通用问题，避免依赖具体 KB 内容；不带 KB 走全局检索
        payload = {
            "question": "请介绍一下退货政策的主要内容",
            "knowledge_base": None,
            "session_id": None,
            "files": [],
        }
        headers = {"Authorization": f"Bearer {token}"}
        with self.client.post(
            "/api/ask",
            json=payload,
            headers=headers,
            stream=True,
            catch_response=True,
            name="ask(sse)",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"ask status {resp.status_code}")
                return
            done = False
            start = time.time()
            try:
                for raw in resp.iter_lines(decode_unicode=True):
                    if not raw:
                        continue
                    if raw.startswith("event:"):
                        if raw.split(":", 1)[1].strip() == "done":
                            done = True
                            break
                    if time.time() - start > SSE_TIMEOUT:
                        break
            except Exception as e:
                resp.failure(f"sse read error: {e}")
                return
            if done:
                resp.success()
            else:
                resp.failure("sse closed without done event")

    @task(2)
    def knowledge_bases(self):
        token = getattr(self, "token", None)
        if not token:
            return
        self.client.get(
            "/api/knowledge-bases",
            headers={"Authorization": f"Bearer {token}"},
            name="knowledge-bases",
        )

    @task(1)
    def trending(self):
        self.client.get("/api/trending", name="trending")

    @task(1)
    def health(self):
        self.client.get("/api/health", name="health")
