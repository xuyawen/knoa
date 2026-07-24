from typing import Literal

from pydantic import Field, model_validator

from app.models.knowledge import CamelModel

# 多模态附件上限（与 P1-4 上传 20MB 对齐）：
# base64 约为原始字节的 4/3，20MB 原始 ≈ 28MB base64 字符串。
MAX_FILE_B64_LEN = 28_000_000
MAX_FILES_PER_ASK = 5


class ChatFile(CamelModel):
    """多模态输入文件（一期仅 image；audio/video 由 MODEL_CAPABILITIES 开关控制）。

    两种传图方式（互斥，优先 url）：
      - url：前端已直传 OSS，传可访问地址；后端直接拼 image_url 给大模型（不发大 base64）
      - data_b64：纯 base64（不含 `data:<mime>;base64,` 前缀），后端拼回 data URI
    """

    kind: Literal["image", "audio", "video"]
    mime_type: str
    url: str | None = None                 # OSS 直传后的可访问地址
    data_b64: str | None = Field(default=None, max_length=MAX_FILE_B64_LEN)
    name: str | None = None


class AskRequest(CamelModel):
    question: str = Field(default="", max_length=2000)
    knowledge_base: str | None = None
    session_id: str | None = None
    files: list[ChatFile] = Field(default_factory=list)
    # 入口来源：chat=对话页问答，search=智能搜索页（搜索即问答）。
    # 用于 OperationLog 区分埋点，Dashboard 才能分别统计「问答次数」与「搜索次数」。
    mode: str = "chat"
    # ── 模型配置（前端 ModelConfig 页下发，全部可空；空=用后端默认值）──
    model: str | None = None              # 覆盖 user.preferred_model（页面即时生效）
    temperature: float | None = None      # 生成温度
    top_p: float | None = None            # 核采样阈值
    max_tokens: int | None = None         # 单次最大生成长度
    top_k: int | None = None              # 知识库检索召回数量
    source_count: int | None = None       # 最终引用来源数上限
    web_search: bool | None = None        # 是否允许联网搜索
    web_provider: str | None = None       # 联网搜索 provider：auto/bocha/tavily/ddg
    system_prompt: str | None = None      # 追加到系统 Prompt 的自定义人设指令
    concise_mode: bool | None = None      # 简洁模式：回答更精炼

    @model_validator(mode="after")
    def _check_non_empty(self) -> "AskRequest":
        if not self.question.strip() and not self.files:
            raise ValueError("请输入问题或上传图片")
        if len(self.files) > MAX_FILES_PER_ASK:
            raise ValueError(f"单次最多上传 {MAX_FILES_PER_ASK} 个附件")
        return self


class SessionCreateIn(CamelModel):
    title: str | None = None


class SessionOut(CamelModel):
    id: str
    title: str
    updated_at: str
    msg_count: int
    summary: str | None = None


class SessionMessageOut(CamelModel):
    id: str
    role: str
    content: str
    citations: list[int] | None = None
    sources: list | None = None
    attachments: list[dict] | None = None


class SessionDetailOut(CamelModel):
    id: str
    title: str
    summary: str | None = None
    messages: list[SessionMessageOut]


# ── 检索记录（RecordsView 服务端分页）──

class RecordOut(CamelModel):
    """一条检索记录 = 一次 user 提问 + 紧跟的 assistant 回答的元数据快照。"""
    id: str                          # "{sessionId}-{msgIndex}"
    session_id: str
    session_title: str
    question: str
    answer: str
    sources: list | None = None      # 原始 sources JSONB（展开时用）
    source_count: int = 0
    kb_count: int = 0
    web_count: int = 0
    graph_count: int = 0
    created_at: str                  # 取自 session.updated_at 或消息 created_at
