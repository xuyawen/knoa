import re
import uuid
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.base import LLMProvider
from app.core.rag.retriever import HybridRetriever
from app.core.store.redis_store import RedisStore
from app.db import ChatMessage, ChatSession
from app.models.knowledge import SourceItemOut

try:
    from langsmith import traceable
except ImportError:
    def traceable(**kwargs):
        def decorator(fn):
            return fn
        return decorator


class RAGPipeline:
    def __init__(
        self,
        retriever: HybridRetriever,
        llm: LLMProvider,
        redis: RedisStore,
        db: AsyncSession,
    ):
        self.retriever = retriever
        self.llm = llm
        self.redis = redis
        self.db = db

    @traceable(name="rag_pipeline", tags=["rag", "stream"])
    async def stream_answer(
        self,
        question: str,
        kb_id: str | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[dict]:
        try:
            # 1. 获取或创建会话
            session = await self._get_or_create_session(session_id, question)

            # 2. 保存用户消息
            self.db.add(ChatMessage(session_id=session.id, role="user", content=question))
            await self.db.flush()

            # 3. 更新 trending 计数
            try:
                await self.redis.incr_trending(question)
            except Exception:
                pass  # ponytail: Redis 不可用不影响问答

            # 4. 检索
            retrieved = await self.retriever.retrieve(question, kb_id, top_k=5)

            # 5. 发送 sources 事件
            sources = [
                SourceItemOut(
                    id=r["id"], kb=r["kb"], title=r["title"],
                    snippet=r["snippet"], confidence=r["confidence"],
                ).model_dump(by_alias=True)
                for r in retrieved
            ]
            yield {"event": "sources", "data": sources}

            # 6. 构建 prompt + 流式生成
            messages = self._build_prompt(question, retrieved)
            full_answer = ""
            async for delta in self.llm.stream_chat(messages):
                full_answer += delta
                yield {"event": "delta", "data": {"content": delta}}

            # 7. 提取引用 + 保存 assistant 消息
            citations = self._extract_citations(full_answer)
            assistant_msg = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=full_answer,
                citations=citations,
                sources=sources,
            )
            self.db.add(assistant_msg)
            await self.db.commit()

            # 8. 发送 done 事件
            yield {
                "event": "done",
                "data": {
                    "messageId": str(assistant_msg.id),
                    "citations": citations,
                    "sessionId": str(session.id),
                },
            }
        except Exception as e:
            yield {"event": "error", "data": {"message": str(e)}}

    def _build_prompt(self, question: str, retrieved: list[dict]) -> list[dict]:
        context = ""
        for r in retrieved:
            context += f"\n[{r['id']}] {r['title']} ({r['kb']})\n{r['content']}\n"

        system = (
            "你是「知海 Knoa」，一个跨境电商运营知识助手。\n"
            "请基于以下检索到的知识库内容回答用户问题，回答必须忠实于来源内容。\n\n"
            "引用规则：\n"
            "- 引用时使用 [1] [2] 这样的标注，数字对应来源编号\n"
            "- 如果知识库内容不足以回答，明确告知用户\n\n"
            "语气与长度：\n"
            "- 用户只是打招呼或闲聊（如「你好」「在吗」「你是谁」）时，只用一句话友好回应，不要做自我介绍、不要罗列功能清单\n"
            "- 涉及真实业务问题时再展开回答并引用来源\n\n"
            f"知识库来源：\n{context}"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]

    def _extract_citations(self, text: str) -> list[int]:
        matches = re.findall(r"\[(\d+)\]", text)
        return sorted(set(int(m) for m in matches))

    async def _get_or_create_session(self, session_id: str | None, question: str) -> ChatSession:
        if session_id:
            result = await self.db.execute(
                select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
            )
            session = result.scalar_one_or_none()
            if session:
                return session
        session = ChatSession(title=question[:50])
        self.db.add(session)
        await self.db.flush()
        return session
