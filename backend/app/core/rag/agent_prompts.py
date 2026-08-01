"""Agentic RAG 的提示词与启发式预分类（从 agent.py 拆出，纯静态定义无副作用）。

- TOOLS_SCHEMA / AGENT_SYSTEM_PROMPT：route 决策用的工具说明与系统提示
- INTENT_PROMPT / ROLL_SUMMARY_SYSTEM：意图分类与滚动摘要的系统提示
- should_skip_retrieval / should_web_search：正则启发式，跳过昂贵的 LLM 决策
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Tool Schemas (OpenAI function calling format)
# ---------------------------------------------------------------------------

TOOLS_SCHEMA: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "retrieve",
            "description": (
                "从知识库中检索与用户问题相关的文档片段。"
                "使用向量语义检索+BM25关键词检索混合搜索。"
                "当问题涉及具体业务知识、运营策略、合规要求时应调用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用于检索的查询词，可以是原始问题或提炼后的关键词",
                    },
                    "reason": {
                        "type": "string",
                        "description": "为什么需要检索这个问题（简短说明）",
                    },
                },
                "required": ["query", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "supplement_search",
            "description": (
                "当首次检索结果不够充分时，用更精确的查询词进行补充检索。"
                "适用于：首次结果相关性低、覆盖面不够、需要不同角度信息的情况。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "refined_query": {
                        "type": "string",
                        "description": "精炼后的检索词，应比首次查询更聚焦或换一个角度",
                    },
                    "gap_description": {
                        "type": "string",
                        "description": "当前缺失了什么信息，为什么要换个方式搜",
                    },
                },
                "required": ["refined_query", "gap_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "联网搜索实时/外部信息。当需要查询知识库未覆盖的最新政策、"
                "实时汇率/股价、新闻事件、或任何需要联网才能确认的事实时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用于联网搜索的查询词",
                    },
                    "reason": {
                        "type": "string",
                        "description": "为什么需要联网搜索（简短说明）",
                    },
                },
                "required": ["query", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_documents",
            "description": (
                "查询知识库文档的结构化元数据（标题、上传时间、状态等），按时间排序。"
                "当用户问“最近新增了哪些文档”“最近上传了什么”“有多少文档”等"
                "关于文档列表/时间/数量的元数据问题时使用，而不是语义检索。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sort_by": {
                        "type": "string",
                        "enum": ["created_at", "updated_at"],
                        "description": "排序字段，默认 created_at",
                    },
                    "order": {
                        "type": "string",
                        "enum": ["desc", "asc"],
                        "description": "排序方向，默认 desc（最新在前）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数，默认 10，最大 30",
                    },
                    "reason": {
                        "type": "string",
                        "description": "为什么要查询文档元数据",
                    },
                },
                "required": ["reason"],
            },
        },
    },
]

# System prompt for agent routing
AGENT_SYSTEM_PROMPT = """你是「知海 Knoa」的智能问答路由器。你的任务是分析用户问题并决定最佳处理策略。

## 可选动作
1. **直接回答 (direct_answer)** — 不调用任何工具，直接回复。
   适用场景：打招呼/闲聊（你好、hi、在吗、谢谢等）、常识性问题、纯寒暄。

2. **调用 retrieve 工具** — 从知识库检索相关文档后回答。
   适用场景：涉及业务知识、运营策略、平台规则、选品方法等问题。

3. **调用 supplement_search 工具** — 当已有检索结果不够充分时，用更精准的关键词再次检索。
   适用场景：首次结果相关性低、信息覆盖不全、需要从其他角度查找。

4. **调用 web_search 工具** — 联网搜索实时/外部信息。
   适用场景：汇率/股价/金价等实时数据、最新政策或平台公告、新闻事件、
   知识库明显过时的内容、或任何需要联网才能确认的事实。

5. **调用 query_documents 工具** — 查询文档元数据（标题、上传时间、状态），按时间排序。
   适用场景：用户问“最近新增了哪些文档”“最近上传了什么”“有哪些新文档”“文档数量”等
   关于文档列表、时间、数量的元数据问题。注意：这类问题不是语义检索，是结构化查询。

## 判断原则
- **核心原则：当用户询问知识库内的具体内容、文档信息、业务细节时，必须先调用 retrieve 检索，绝对不能直接回答。** 你不知道库里实际存了什么，直接回答一定是幻觉。
- **元数据问题用 query_documents：** 用户问“最近新增”“上传了什么”“有多少文档”时，用 query_documents 而不是 retrieve。语义检索无法按时间排序，结构化查询才能给出准确的文档列表。
- 问题越具体/专业，越应该走检索路径
- 如果问题包含多个子问题或需要对比分析，优先做一次全面检索
- 只有在确实缺少关键信息时才触发补充检索（控制成本）
- 天气、时间日期类问题：若无知识库答案，用 web_search 联网查询实时信息，不要凭记忆编造
- 汇率/股价/最新政策/新闻等实时或易变信息：优先 web_search 联网核实
- 知识库能回答的运营/合规问题优先走 retrieve，不要无谓联网
- 回答必须简洁务实，不要自我介绍或罗列功能
- **宁可检索后说“库中未找到相关内容”，也不要不检索就直接编造答案**

## 输出格式
根据判断选择一个动作执行。如果是直接回答，就在 content 里写回复内容；
如果需要检索或联网，就调用对应的工具（retrieve / supplement_search / web_search / query_documents）并填好参数。"""


# ---------------------------------------------------------------------------
# 快速预分类：明显不需要检索的问题，跳过昂贵的 LLM tool_call（省 15~40s）
# ---------------------------------------------------------------------------

_SKIP_RETRIEVAL_PATTERNS: list[re.Pattern] = [
    re.compile(r"现在(几点|什么时间|几号|星期几|农历)", re.I),
    re.compile(r"^(现在)?(几点了?|什么时间|今天星期|今天几号)", re.I),
    re.compile(r"^[0-9]+[+\-*/][0-9]+", re.I),  # 纯数学计算（阿拉伯符号）
    re.compile(r"\d+\s*(的\s*)?(乘以|乘|×|除以|除|÷)\s*\d+|\d+\s*的\s*\d+\s*倍", re.I),  # 中文算式（125 乘以 8 / 100 的 3 倍）
    re.compile(r"^(翻译|translate) +", re.I),  # 翻译请求
]


def should_skip_retrieval(question: str) -> bool:
    """快速判断是否应该跳过 RAG 检索（纯启发式，不调 LLM）。"""
    q = question.strip()
    return any(p.search(q) for p in _SKIP_RETRIEVAL_PATTERNS)


# 需要联网搜索实时/易变信息的快速预分类（避免 LLM 凭记忆编造）
_WEB_SEARCH_PATTERNS: list[re.Pattern] = [
    re.compile(r"(今天|明天|后天|本周|下周|这周|那周).*?(天气|气温|温度|下雨|下雪|晴|阴|多云|台风|暴雨|雾霾)", re.I),
    re.compile(r"(天气|气温|温度).*(怎么|怎么样|如何|多少度|几度|会.*吗|呢？?$)", re.I),
    re.compile(r"(汇率|美金|美元|人民币|人民币兑|兑美元|eur|gbp|jpy).*(多少|走势|换算|现在|今日|今天)", re.I),
    re.compile(r"(美元|人民币|欧元|英镑|日元|加元).*(兑|汇率|换|多少)", re.I),
    re.compile(r"(金价|黄金价格|原油|油价|比特币|btc|eth|股票|股价|纳斯达克|道琼斯).*(多少|报价|行情|现在|今日)", re.I),
    re.compile(r"(最新|新的|近期|2024|2025|今年|本月).*(政策|规定|公告|费率|费用|关税|税)", re.I),
    re.compile(r"(新闻|热点|事件|刚刚|今天).*(发生|发布|宣布|消息)", re.I),
    re.compile(r"(amazon|亚马逊).*(new|update|policy|fee|fba).*(2024|2025|recent|latest)", re.I),
]


def should_web_search(question: str) -> bool:
    """判断是否需要联网搜索实时/易变信息（避免 LLM 凭记忆编造）。"""
    q = question.strip()
    return any(p.search(q) for p in _WEB_SEARCH_PATTERNS)


INTENT_PROMPT = (
    "你是企业知识助手「知海 Knoa」的意图分类器。\n"
    "只输出一行 JSON，不要任何解释、标点或代码块围栏：\n"
    '{"intent": "<标签>", "query": "<检索词>"}\n'
    "标签含义：\n"
    "- greeting：打招呼 / 闲聊 / 常识 / 时间 / 简单寒暄（不涉及具体业务知识）\n"
    "- web_search：需要实时或易变信息（天气、股价、汇率、最新政策新闻）\n"
    "- simple：可用单篇知识库检索直接回答的具体业务问题\n"
    "- complex：需要跨实体 / 跨流程关联推理的复杂业务问题"
    "（如「A 流程和 B 流程的关系」「某政策对物流的影响」）\n"
    "query 字段：intent 为 simple/complex 时，填从问题提炼的检索关键词"
    "（结合上下文消解「这个/那个」等指代、去掉口语化措辞、保留实体+动作）；"
    "greeting/web_search 时填原问题即可。"
)


ROLL_SUMMARY_SYSTEM = (
    "你是一个对话摘要压缩器。给定某企业知识助手会话里「较早的对话片段」，"
    "请把它压缩成一段简洁的摘要，供后续轮次理解上下文。\n"
    "规则：\n"
    "1. 保留关键事实：用户提到的产品/实体名称、已确认的结论、已做的决策、待办、用户偏好。\n"
    "2. 丢弃寒暄、重复、与后续无关的细节。\n"
    "3. 若给出「已有摘要」，请把新对话与已有摘要融合，输出一段连贯的新摘要（不要重复罗列）。\n"
    "4. 语言与用户一致（中文则用中文）。\n"
    "5. 输出一段紧凑的自然语言摘要，不超过 200 字。不要使用 markdown、不要解释。"
)
