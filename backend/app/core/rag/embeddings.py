from openai import AsyncOpenAI

from app.config import settings


class EmbeddingModel:
    """OpenAI-compatible embeddings API 封装"""

    def __init__(self, model_name: str = ""):
        self.client = AsyncOpenAI(
            base_url=settings.EMBEDDING_BASE_URL,
            api_key=settings.EMBEDDING_API_KEY,
        )
        self.model = model_name or settings.EMBEDDING_MODEL
        self.dim = settings.EMBEDDING_DIM

    async def embed(self, texts: list[str], batch_size: int = 10) -> list[list[float]]:
        """批量编码文档, DashScope 限制每批 <= 10"""
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = await self.client.embeddings.create(model=self.model, input=batch)
            all_embeddings.extend(d.embedding for d in sorted(resp.data, key=lambda x: x.index))
        return all_embeddings

    async def embed_query(self, text: str) -> list[float]:
        """编码查询文本"""
        resp = await self.client.embeddings.create(model=self.model, input=text)
        return resp.data[0].embedding
