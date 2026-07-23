"""按 URL 拉取文件字节（OSS 直传后后端回抓解析用）。

与 storage.py 同款零依赖风格：httpx 直连，不引 SDK。
关键防护：
  - max_bytes 上限，流式读取避免大文件撑爆内存
  - 调用方需先用 oss.normalize_url 做 SSRF 白名单校验（只允许本 OSS 桶 host），
    本函数不再重复校验 host，只负责流式取字节。
"""
from __future__ import annotations

import httpx


async def fetch_url_bytes(url: str, max_bytes: int = 100 * 1024 * 1024) -> bytes:
    """流式拉取 URL 字节，超过 max_bytes 抛 ValueError。"""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"文件超过大小上限 {max_bytes} 字节")
                chunks.append(chunk)
            return b"".join(chunks)
