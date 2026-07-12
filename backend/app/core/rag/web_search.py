"""联网搜索客户端（可插拔 provider）。

设计约束：项目 venv 无法 pip 安装第三方包，因此只依赖已安装的 httpx
（与 LLM/Embedding 调用同源），并尽量用标准库做结果解析。

Provider 策略（优先级从高到低）：
  - BoCha 博查 web-search（需 BOCHA_API_KEY，中文/国内信息覆盖好，质量最稳）
  - Tavily API（需 TAVILY_API_KEY，专为 LLM 检索设计）
  - 二者均无 key 时，回退 DuckDuckGo HTML 接口（无需 key，httpx + 正则解析）
  - 任一 provider 失败都自动降级到下一个，全失败才返回空列表

返回结构统一为 SourceItemOut 兼容的 dict：
  {"id": int, "title": str, "url": str, "snippet": str,
   "source_type": "web", "kb": "web", "chunk_id": "web:N"}
注意 id 由调用方（agent）按 all_sources 当前长度重新连续编号，避免与知识库
来源（1..N）撞号。
"""
from __future__ import annotations

import html
import re
import urllib.parse

import httpx

from app.config import settings


class WebSearcher:
    """联网搜索封装（异步）。"""

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

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """返回联网检索结果（统一结构）。provider 依优先级尝试，异常逐级降级，全失败返回空列表。"""
        if settings.BOCHA_API_KEY:
            try:
                return await self._search_bocha(query, max_results)
            except Exception as e:  # BoCha 失败降级到 Tavily / DDG，保证联网能力可用
                print(f"[web_search] BoCha failed, fallback: {e}")
        if settings.TAVILY_API_KEY:
            try:
                return await self._search_tavily(query, max_results)
            except Exception as e:
                print(f"[web_search] Tavily failed, fallback to DDG: {e}")
        try:
            return await self._search_ddg(query, max_results)
        except Exception as e:
            print(f"[web_search] DDG failed: {e}")
            return []

    # ── Tavily（需 key）──
    async def _search_tavily(self, query: str, max_results: int) -> list[dict]:
        resp = await self._client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        out: list[dict] = []
        for i, r in enumerate(data.get("results", [])[:max_results], 1):
            out.append(
                {
                    "id": i,
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": (r.get("content") or "")[:300],
                    "source_type": "web",
                    "kb": "web",
                    "chunk_id": f"web:{i}",
                }
            )
        return out

    # ── DuckDuckGo HTML（无 key 兜底）──
    async def _search_ddg(self, query: str, max_results: int) -> list[dict]:
        resp = await self._client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
        )
        resp.raise_for_status()
        return self._parse_ddg_html(resp.text, max_results)

    @staticmethod
    def _parse_ddg_html(html_text: str, max_results: int) -> list[dict]:
        # 标题+链接：class="result__a" 的 <a>
        # 片段：class="result__snippet" 的 <a>
        title_re = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.S
        )
        snip_re = re.compile(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', re.S)

        titles = title_re.findall(html_text)
        snippets = snip_re.findall(html_text)

        out: list[dict] = []
        for i, (href, raw_title) in enumerate(titles[:max_results], 1):
            title = _strip_tags(raw_title)
            if not title:
                continue
            snippet = ""
            if i - 1 < len(snippets):
                snippet = _strip_tags(snippets[i - 1])[:300]
            out.append(
                {
                    "id": i,
                    "title": title,
                    "url": _extract_ddg_url(href),
                    "snippet": snippet,
                    "source_type": "web",
                    "kb": "web",
                    "chunk_id": f"web:{i}",
                }
            )
        return out


    # ── BoCha 博查 web-search（需 key，中文检索质量最佳）──
    async def _search_bocha(self, query: str, max_results: int) -> list[dict]:
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
        # 否则会把空数据误判为成功，阻断向 Tavily/DDG 的降级。
        if data.get("code") not in (200, None):
            raise RuntimeError(f"BoCha error code={data.get('code')} msg={data.get('msg')}")
        return self._parse_bocha(data, max_results)

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


def _strip_tags(s: str) -> str:
    s = re.sub(r"<.*?>", "", s)
    return html.unescape(s).strip()


def _extract_ddg_url(href: str) -> str:
    """DDG 结果链接形如 /redirect/?uddg=<encoded_url>&...，提取真实 url。"""
    m = re.search(r"uddg=([^&]+)", href)
    if m:
        return urllib.parse.unquote(m.group(1))
    return href
