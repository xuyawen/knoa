"""Mem0 轻量自研版 —— 基于 pgvector(JSONB) + LLM 抽取的长期记忆。

设计目标（对照 Mem0 官方库的核心思想）：
- 抽取：每轮问答后，用 LLM 从对话里抽出「值得长期记住」的事实 / 偏好 / 反馈。
- 存储：每条记忆带 embedding（JSONB + numpy 余弦），与 DocChunk 完全同方案。
- 检索：下一轮问答时，按 user_id 取该用户的记忆做语义召回，注入 prompt。
- 冲突 / 去重：新增记忆时与已有记忆算余弦，超过阈值则更新旧记忆（upsert），
  而非无脑追加，避免「用户改了偏好却同时存在新旧两条矛盾记忆」。

为什么不直接用 Mem0 开源库？
本环境 venv 无法 pip 安装第三方包（见 MEMORY.md），且项目已自研
hybrid retriever + JSONB 向量方案，复用同一套即可，零新依赖、零迁移成本。
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm.base import LLMProvider
from app.core.rag.embeddings import EmbeddingModel
from app.db import Memory

logger = logging.getLogger(__name__)

_EXTRACT_SYSTEM = (
    "你是一个记忆抽取器。给定用户与跨境电商运营知识助手『知海 Knoa』的一段问答，"
    "请抽取其中值得长期记住的信息。\n"
    "规则：\n"
    "1. 只抽取可跨会话复用的长期信息：用户偏好（如『用中文回复』『回答要简洁』）、"
    "长期事实（如『我们公司主营 3C 配件』）、对助手行为的反馈 / 纠正。\n"
    "2. 不要抽取仅当前问题才用到的一次性事实，也不要复述用户刚问的问题。\n"
    "3. 若本轮没有任何值得长期记忆的信息，返回空数组 []。\n"
    "4. 输出严格为 JSON 数组，每个元素形如 "
    '{"type": "preference|fact|feedback", "content": "简洁陈述，不超过30字"}。'
    "不要使用 markdown 代码块，不要输出任何解释性文字。"
)


def _coerce_list(obj) -> list:
    """把 LLM 返回的各类 JSON 归一化成记忆列表。"""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        # 兼容 {"memories": [...]} 这类包装
        for k in ("memories", "memory", "items", "results"):
            if isinstance(obj.get(k), list):
                return obj[k]
    return []


def _extract_json_array(text: str) -> list:
    """从 LLM 输出里稳健抽取 JSON 数组（兼容 ```json 围栏 / 前后缀噪声）。"""
    text = (text or "").strip()
    if not text:
        return []
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    # 直接解析
    try:
        return _coerce_list(json.loads(text))
    except (json.JSONDecodeError, ValueError):
        pass
    # 截取第一个 [ 到最后一个 ]
    s, e = text.find("["), text.rfind("]")
    if s != -1 and e != -1 and e > s:
        try:
            return _coerce_list(json.loads(text[s : e + 1]))
        except (json.JSONDecodeError, ValueError):
            pass
    # 退一步：尝试找 {...} 对象
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            return _coerce_list(json.loads(text[s : e + 1]))
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def _cosine(a, b) -> float:
    """余弦相似度（numpy，与 DocChunk 检索同实现）。"""
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


class MemoryStore:
    """用户长期记忆的抽取 + 存储 + 检索。"""

    def __init__(self, embedder: EmbeddingModel):
        self.embedder = embedder

    async def extract(
        self, llm: LLMProvider, question: str, answer: str
    ) -> list[dict]:
        """用 LLM 从一问答对里抽取记忆。任何失败都返回 []，绝不阻断主链路。"""
        if not settings.MEMORY_ENABLED:
            return []
        user_prompt = (
            f"用户问题：{question}\n\n"
            f"助手回答：{answer}\n\n"
            "请输出需要长期记住的记忆数组："
        )
        try:
            raw = await llm.chat(
                [
                    {"role": "system", "content": _EXTRACT_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
            )
        except Exception as e:  # LLM 不可用（沙箱 / 断网）→ 跳过，不影响回答
            logger.warning("memory extract skipped (llm failed): %s", e)
            return []
        items = _extract_json_array(raw)
        cleaned: list[dict] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            content = (it.get("content") or "").strip()
            if not content:
                continue
            cleaned.append(
                {"type": str(it.get("type", "")).strip() or None, "content": content}
            )
        return cleaned

    async def retrieve(
        self, user_id, query: str, db: AsyncSession, top_k: int | None = None
    ) -> list[str]:
        """语义召回该用户最相关的 top_k 条记忆原文。"""
        top_k = top_k or settings.MEMORY_TOP_K
        rows = await self._load_user_memories(user_id, db)
        if not rows:
            return []
        q_emb = await self.embedder.embed_query(query)
        scored = []
        for r in rows:
            if not r.embedding:
                continue
            scored.append((_cosine(q_emb, r.embedding), r.content))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    async def save(
        self, user_id, memories: Sequence[dict], db: AsyncSession
    ) -> None:
        """写入记忆，带相似性去重（upsert）：与已有记忆相似度超阈值则更新。"""
        if not memories:
            return
        rows = await self._load_user_memories(user_id, db)
        texts = [m["content"] for m in memories]
        new_embs = await self.embedder.embed(texts)
        for m, emb in zip(memories, new_embs):
            # 找一个最相似的旧记忆
            best_idx, best_sim = -1, -1.0
            for i, r in enumerate(rows):
                if not r.embedding:
                    continue
                sim = _cosine(emb, r.embedding)
                if sim > best_sim:
                    best_sim, best_idx = sim, i
            if best_idx >= 0 and best_sim >= settings.MEMORY_SIM_THRESHOLD:
                # 更新而非新增（冲突消解：偏好变了就覆盖旧的）
                rows[best_idx].content = m["content"]
                rows[best_idx].embedding = emb
                rows[best_idx].meta_type = m.get("type")
                continue
            db.add(
                Memory(
                    user_id=user_id,
                    content=m["content"],
                    embedding=emb,
                    meta_type=m.get("type"),
                )
            )
        await db.commit()

    @staticmethod
    async def _load_user_memories(user_id, db: AsyncSession) -> list:
        result = await db.execute(select(Memory).where(Memory.user_id == user_id))
        return list(result.scalars().all())
