"""测试替身：无需真实 LLM / Embedding / Redis / Graph 即可跑通问答与摄入链路。

- FakeEmbedder：用文本哈希生成确定性向量，并让「词重叠」提升余弦相似度，
  从而让基于 numpy 余弦 + BM25 + RRF 的混合检索能正确召回相关 chunk。
- FakeLLM：按调用次数驱动 Agent 决策循环（先 retrieve 再 direct_answer），
  并流式产出固定回答，验证 SSE 问答链路不会因缺 key 而崩。
- FakeRedis / FakeGraph：把外部依赖变成 no-op，隔离测试。
"""

import hashlib
import re

import numpy as np

DIM = 1536


def _tokens(text: str) -> list[str]:
    """中文无空格，按「整句」分词会让整段塌缩成一个 token，无法体现词重叠。

    这里退一步用「字符级 + ASCII 词」切分：
    - CJK 单字各成一个 token（中文语义的最小重叠单元）；
    - 连续 ASCII 字母/数字成词。
    这样形似「退款/申请」的 query 与正文之间能稳定产生高余弦重叠，
    让向量检索与 BM25 方向一致，把正确 chunk 排到前面。
    """
    toks: list[str] = []
    buf: list[str] = []
    for ch in text:
        o = ord(ch)
        if ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9") or ch == "_":
            buf.append(ch)
        else:
            if buf:
                toks.append("".join(buf))
                buf = []
            if 0x4E00 <= o <= 0x9FFF:
                toks.append(ch)
    if buf:
        toks.append("".join(buf))
    return toks


def _fake_vec(text: str, dim: int = DIM) -> list[float]:
    """确定性「词袋」向量：每个 token 哈希到固定维度并 +1。

    - 不含随机基向量（避免噪声淹没词重叠信号）。
    - 归一化后余弦相似度 ≈ 词袋重叠度。
    因此 query 与正文共享的汉字越多，余弦越高，检索排序正确且稳定。
    """
    v = np.zeros(dim, dtype=np.float32)
    for tok in _tokens(text):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest()[:8], 16) % dim
        v[h] += 1.0
    norm = float(np.linalg.norm(v))
    return (v / norm).tolist() if norm else v.tolist()


class FakeEmbedder:
    """替代 EmbeddingModel：embed / embed_query 返回确定性向量。"""

    def __init__(self, *args, **kwargs):
        self.dim = DIM

    async def embed(self, texts, batch_size: int = 10):
        return [_fake_vec(t) for t in texts]

    async def embed_query(self, text: str):
        return _fake_vec(text)


class FakeLLM:
    """替代 OpenAICompatProvider：驱动 agent 决策循环。

    第 1 次 tool_call → retrieve；第 2 次 → direct_answer（带内容）。
    stream_chat 产出固定 token，验证生成链路。
    """

    def __init__(self):
        self.calls = 0

    async def tool_call(self, messages, tools=None, temperature=None):
        from app.core.llm.base import ToolCallResult

        self.calls += 1
        if self.calls == 1:
            return ToolCallResult(
                name="retrieve",
                arguments={"query": "退款政策"},
                raw_text="需要检索知识库",
            )
        return ToolCallResult(
            name="direct_answer",
            arguments={"content": "您可以申请 7 天无理由退款。"},
            raw_text="已有足够信息，直接回答",
        )

    async def stream_chat(self, messages, temperature=None):
        for tok in ["您可以", "申请", "7 天无理由退款。"]:
            yield tok

    async def chat(self, messages, temperature=None) -> str:
        return "您可以申请 7 天无理由退款。"


class FakeRedis:
    """替代 RedisStore：所有方法 no-op。"""

    async def incr_trending(self, question: str):
        return None

    async def get_trending(self, limit: int = 10):
        return []

    async def close(self):
        return None


class FakeGraph:
    """替代 GraphStore：extract 静默跳过，避免测试时调 LLM 抽实体。"""

    def __init__(self, llm=None, embedder=None):
        self.enabled = False

    async def extract(self, kb_id, title, chunk_infos, db):
        return None

    async def retrieve_related_chunks(self, *args, **kwargs):
        return []
