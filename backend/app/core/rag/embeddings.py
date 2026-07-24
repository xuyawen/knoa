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
            # dimensions 仅 v3/v4 等支持自定义维度的模型生效；显式传维度，
            # 确保返回向量长度 == settings.EMBEDDING_DIM（与库内向量一致，否则检索维度错配全空）。
            resp = await self.client.embeddings.create(
                model=self.model, input=batch, dimensions=self.dim
            )
            all_embeddings.extend(d.embedding for d in sorted(resp.data, key=lambda x: x.index))
        return all_embeddings

    async def embed_query(self, text: str) -> list[float]:
        """编码查询文本"""
        resp = await self.client.embeddings.create(
            model=self.model, input=text, dimensions=self.dim
        )
        data = resp.data
        if not data:
            raise ValueError(f"embedding 服务返回空结果 (input={text[:50]!r})")
        return data[0].embedding
