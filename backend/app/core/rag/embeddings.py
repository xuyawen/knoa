from openai import AsyncOpenAI

from app.config import settings


class EmbeddingModel:
    """OpenAI-compatible embeddings API 封装"""

    def __init__(self, model_name: str = ""):
        # ponytail: 用单独的 embedding 配置, 可与 LLM 不同提供商
        self.client = AsyncOpenAI(
            base_url=settings.EMBEDDING_BASE_URL,
            api_key=settings.EMBEDDING_API_KEY,
        )
        self.model = model_name or settings.EMBEDDING_MODEL
        self.dim = settings.EMBEDDING_DIM

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量编码文档"""
        resp = await self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [d.embedding for d in sorted(resp.data, key=lambda x: x.index)]

    async def embed_query(self, text: str) -> list[float]:
        """编码查询文本"""
        resp = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return resp.data[0].embedding
