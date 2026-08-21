"""联网搜索客户端（国内服务 BoCha 博查）。

设计约束：项目 venv 无法 pip 安装第三方包，因此只依赖已安装的 httpx
（与 LLM/Embedding 调用同源），并尽量用标准库做结果解析。

Provider 策略：
  - 仅使用国内服务 BoCha 博查 web-search（需 BOCHA_API_KEY，中文信息覆盖好）；
  - 境外检索服务（Tavily / DuckDuckGo 等）已移除——生产服务器网络不可达，
    留着只会拖长超时；未配置 key 或调用失败时直接返回空列表，
    由上层 agent 提示「无法获取实时信息」，绝不降级境外服务。

返回结构统一为 SourceItemOut 兼容的 dict：
  {"id": int, "title": str, "url": str, "snippet": str,
   "source_type": "web", "kb": "web", "chunk_id": "web:N"}
注意 id 由调用方（agent）按 all_sources 当前长度重新连续编号，避免与知识库
来源（1..N）撞号。
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class WebSearcher:
    """联网搜索封装（异步，仅 BoCha）。"""

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                )
            },
        )

    async def aclose(self):
        await self._client.aclose()

    async def search(self, query: str, max_results: int = 5, provider: str | None = None) -> list[dict]:
        """返回联网检索结果（统一结构）。

        provider: 'auto'(默认) 或显式 'bocha'（历史值 tavily/ddg 已下线，
                  视同 auto 处理）。未配置 BOCHA_API_KEY 或调用失败返回空列表。
        """
        if provider not in (None, "auto", "bocha"):
            logger.info("web_search provider=%s 已下线，忽略", provider)
        if not settings.BOCHA_API_KEY:
            logger.info("web_search skipped: BOCHA_API_KEY not configured")
            return []
        try:
            return await self._search_bocha(query, max_results)
        except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort, return empty on failure)
            logger.warning("BoCha search failed: %s", e)
            return []

    # ── BoCha 博查 web-search（需 key，中文检索质量最佳）──
    async def _search_bocha(self, query: str, max_results: int, retries: int = 2) -> list[dict]:
        """BoCha 免费额度偶发 429 / 网络抖动：对可重试错误做退避重试，
        避免一遇限流就整条搜索落空、模型被迫答「无法获取实时信息」。

        仅对 429 限流与传输/超时类错误重试；key 无效、配额耗尽（业务 code 非 200）
        属不可重试错误，直接抛出返回空结果。"""
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = await self._client.post(
                    "https://api.bocha.cn/v1/web-search",
                    headers={
                        "Authorization": f"Bearer {settings.BOCHA_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": query,
                        "count": max_results,
                        "freshness": "noLimit",
                        "summary": True,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                # 博查在 key 无效/配额耗尽时仍返回 HTTP 200，需靠顶层 code 判断真实成败，
                # 否则会把空数据误判为成功。
                if data.get("code") not in (200, None):
                    raise RuntimeError(f"BoCha error code={data.get('code')} msg={data.get('msg')}")
                return self._parse_bocha(data, max_results)
            except (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException) as e:
                last_err = e
                status = getattr(getattr(e, "response", None), "status_code", None)
                # 只有 429 限流或传输/超时类错误才退避重试；其余（4xx 业务错误）直接抛出
                if attempt < retries and (status == 429 or isinstance(e, (httpx.TransportError, httpx.TimeoutException))):
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                raise
        assert last_err is not None
        raise last_err

    @staticmethod
    def _parse_bocha(data: dict, max_results: int) -> list[dict]:
        items = data.get("data", {}).get("webPages", {}).get("value", [])
        out: list[dict] = []
        for i, it in enumerate(items[:max_results], 1):
            title = (it.get("name") or it.get("title") or "").strip()
            if not title:
                continue
            url = it.get("url") or ""
            snippet = (
                it.get("summary")
                or it.get("snippet")
                or it.get("description")
                or (it.get("markdown") or "")
            )[:300]
            out.append(
                {
                    "id": i,
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "source_type": "web",
                    "kb": "web",
                    "chunk_id": f"web:{i}",
                }
            )
        return out
