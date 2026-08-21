"""AgenticRAGAgent 的会话持久化层（从 agent.py 拆出，纯 DB/记忆职责）。

SessionMemoryMixin 承载与数据库、长期记忆相关的方法：
  - 会话创建与归属校验（IDOR 防护）
  - 历史消息加载与 LLM messages 回构（含多模态附件）
  - Mem0 长期记忆后台落库
  - 滚动摘要（窗口外旧对话压缩进 ChatSession.summary）

宿主类需提供 self.db / self.llm / self.memory / self.user_id 属性。
"""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.core.rag.agent_prompts import ROLL_SUMMARY_SYSTEM, should_skip_retrieval
from app.database import AsyncSessionLocal
from app.db import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


class SessionMemoryMixin:
    """会话/记忆持久化方法集合，由 AgenticRAGAgent 混入。"""

    async def _save_memory(self, question: str, answer: str) -> None:
        """问答结束后，后台抽取并保存长期记忆（不阻塞已返回的 SSE 流）。

        自己开一个独立 db session，与请求主 session 解耦，
        这样即便生成器已 yield done 并随请求关闭主 session，记忆落库仍可进行。
        """
        if not (self.memory and self.user_id):
            return
        # 打招呼 / 闲聊无需记忆，省一次 LLM 调用
        if should_skip_retrieval(question):
            return
        try:
            async with AsyncSessionLocal() as s:
                memories = await self.memory.extract(self.llm, question, answer)
                if memories:
                    await self.memory.save(self.user_id, memories, s)
        except Exception as e:  # noqa: BLE001  (intentional catch-all: background memory-save task, log and skip on failure)
            logger.warning("memory save failed (skipped): %s", e)

    async def _load_session_history(self, session) -> "tuple[list[dict], str | None]":
        """返回 (保留区原始消息, 滚动摘要文本)。

        保留最近 CONV_SUMMARY_KEEP_RECENT 条原始消息（细节不失真），
        更早的已由后台 _roll_summary 压缩进 session.summary（长会话上下文）。
        summary 取自 ChatSession.summary（由 _roll_summary 异步维护）。
        排除当前轮刚 flush 的 user 消息。
        只取窗口内需要的最新 keep+1 条（SQL 层 LIMIT），避免长会话每轮
        全量加载几百条历史（含大体积多模态附件 JSONB）。
        """
        keep = settings.CONV_SUMMARY_KEEP_RECENT
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(keep + 1)
        )
        all_msgs = list(reversed(result.scalars().all()))

        # 排除最后一条（本轮刚 flush 的 user message）；首条消息则无历史
        if len(all_msgs) > 1:
            all_msgs = all_msgs[:-1]
        else:
            return [], (session.summary or None)

        return self._msgs_to_llm(all_msgs), (session.summary or None)

    def _msgs_to_llm(self, msgs) -> list[dict]:
        """把 ChatMessage 列表回构为 LLM messages（多模态 user 回构 content blocks）。"""
        history: list[dict] = []
        for msg in msgs:
            if msg.role == "user":
                if msg.attachments:
                    content = self._build_user_content(msg.content or "", msg.attachments)
                else:
                    content = msg.content or ""
                history.append({"role": "user", "content": content})
            elif msg.role == "assistant":
                if msg.content:
                    history.append({"role": "assistant", "content": msg.content})
        return history

    @staticmethod
    def _format_history_text(msgs) -> str:
        """把一段历史消息拼成纯文本（给 LLM 做摘要用）。

        多模态图片：只标注「附 N 张图片」，绝不塞 base64（太大且无意义）。
        """
        parts = []
        for m in msgs:
            if m.role == "user":
                extra = ""
                if m.attachments:
                    n = len(m.attachments) if isinstance(m.attachments, list) else 0
                    if n:
                        extra = f"（附 {n} 张图片）"
                parts.append(f"用户：{(m.content or '').strip()}{extra}")
            elif m.role == "assistant" and m.content:
                parts.append(f"助手：{m.content.strip()}")
        return "\n".join(parts)

    async def _roll_summary(self, session_id: uuid.UUID) -> None:
        """后台滚动摘要：把窗口外的旧对话段压缩进 ChatSession.summary。

        与 Mem0 的 _save_memory 同源模式——自己开独立 db session，
        不阻塞已返回的 SSE 流；本轮 user+assistant 落库后才触发，
        故能读到完整历史。下一轮提问时 summary 才被注入
        （滚动摘要本就是给未来轮次用的）。

        触发闸门（省成本）：
        - 历史总条数 <= KEEP_RECENT：不摘要
        - 窗口外、尚未摘要的段为空：跳过
        - 非首次且累计新段 < STEP：跳过（每积累 STEP 条才重摘一次）
        """
        if not settings.CONV_SUMMARY_ENABLED:
            return
        try:
            async with AsyncSessionLocal() as s:
                sess = (
                    await s.execute(
                        select(ChatSession).where(ChatSession.id == session_id)
                    )
                ).scalar_one_or_none()
                if not sess:
                    return
                msgs = (
                    await s.execute(
                        select(ChatMessage)
                        .where(ChatMessage.session_id == session_id)
                        .order_by(ChatMessage.created_at.asc())
                    )
                ).scalars().all()

                n = len(msgs)
                keep = settings.CONV_SUMMARY_KEEP_RECENT
                if n <= keep:
                    return  # 还不够长，无需摘要

                window_start = n - keep  # 窗口外（需摘要）/ 窗口内（保留）分界
                already = sess.summarized_count or 0
                if window_start <= already:
                    return  # 没有新窗口外消息需要摘要
                new_segment_count = window_start - already
                if already > 0 and new_segment_count < settings.CONV_SUMMARY_STEP:
                    return  # 非首次：累计新段未达 STEP，先不重摘（省 LLM 调用）

                segment_text = self._format_history_text(msgs[already:window_start])
                if not segment_text.strip():
                    # 边界前移，避免反复空尝试
                    sess.summarized_count = window_start
                    await s.commit()
                    return

                prompt = [
                    {"role": "system", "content": ROLL_SUMMARY_SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"[已有摘要]\n{sess.summary or '（无）'}\n\n"
                            f"[本轮需要压缩的新对话]\n{segment_text}"
                        ),
                    },
                ]
                try:
                    new_summary = (await self.llm.chat(prompt, temperature=0.2)).strip()
                except Exception as e:  # noqa: BLE001  (intentional catch-all: best-effort, skip summary if LLM fails)
                    logger.warning("roll summary llm failed (skip): %s", e)
                    return
                if not new_summary:
                    sess.summarized_count = window_start
                    await s.commit()
                    return

                sess.summary = new_summary
                sess.summarized_count = window_start
                await s.commit()
        except Exception as e:  # noqa: BLE001  (intentional catch-all: background summary task, log and skip on failure)
            logger.warning("roll summary failed (skipped): %s", e)

    @staticmethod
    def _build_user_content(question: str, files: "list[dict] | None") -> "str | list[dict]":
        """把文本 + 附件拼成 OpenAI 多模态 content。

        纯文本问题 → 返回 str;带附件 → 返回 content blocks list。
        - image：拼 image_url（OSS url 优先，否则 data URI）；
        - document：ask 路由已提取文本，这里拼成 text block 注入上下文，
          任何文本模型都能消费（不依赖视觉能力）。
        能力 gating 在 ask 路由完成，此处只做渲染。
        """
        if not files:
            return question
        blocks: list[dict] = []
        if question.strip():
            blocks.append({"type": "text", "text": question})
        for f in files:
            if f.get("kind") == "image":
                # OSS 直传优先用 url（大模型直接拉取，省去大 base64 往返）；
                # 否则回退旧 data URI 路径
                if f.get("url"):
                    blocks.append({
                        "type": "image_url",
                        "image_url": {"url": f["url"]},
                    })
                elif f.get("data_b64"):
                    blocks.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{f['mime_type']};base64,{f['data_b64']}"},
                    })
            elif f.get("kind") == "document" and f.get("text"):
                blocks.append({
                    "type": "text",
                    "text": f"【附件 {f.get('name') or '文档'} 的正文内容】\n{f['text']}",
                })
        return blocks if blocks else question

    async def _get_or_create_session(self, session_id: str | None, question: str) -> ChatSession:
        if session_id:
            # 前端传入的 session_id 可能非合法 UUID，先校验再查库，
            # 否则 uuid.UUID() 抛 ValueError → 被顶层兜底成 500，应明确 400。
            try:
                sid = uuid.UUID(session_id)
            except (ValueError, AttributeError, TypeError):
                raise HTTPException(status_code=400, detail="无效的会话 ID") from None
            result = await self.db.execute(select(ChatSession).where(ChatSession.id == sid))
            s = result.scalar_one_or_none()
            if s:
                # 会话归属校验：阻止拿到他人 session_id 后读其历史上下文/
                # 往其会话写消息（IDOR）。用 404 而非 403，不向探测者泄露会话存在性。
                if s.user_id and self.user_id and str(s.user_id) != str(self.user_id):
                    raise HTTPException(status_code=404, detail="会话不存在")
                return s
        # 隐式建会话（主聊天里直接提问、未指定 session_id 时）必须绑定
        # user_id，否则 list_sessions 按 user_id 过滤会把该会话排除，
        # 导致「回复能显示、sessionId 也返回了，却在历史列表里找不到」。
        s = ChatSession(title=question[:50], user_id=self.user_id)
        self.db.add(s)
        await self.db.flush()
        return s
