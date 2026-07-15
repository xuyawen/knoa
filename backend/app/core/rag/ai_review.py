from __future__ import annotations

import json

import numpy as np
from sqlalchemy import select

from app.config import settings
from app.core.llm.openai_compat import OpenAICompatProvider
from app.core.rag.chunker import MarkdownChunker
from app.core.rag.embeddings import EmbeddingModel
from app.db import DocChunk, Document, KnowledgeBase

# 相似度阈值：超过即判定为疑似重复，纳入 AI 建议
SIMILARITY_THRESHOLD = 0.82


def _build_review_prompt(
    title: str, content: str, findings: list[dict], kb_names: list[str]
) -> str:
    ftext = (
        json.dumps(findings, ensure_ascii=False, indent=2)
        if findings
        else "（未检测到高相似内容）"
    )
    kb_list = "、".join(kb_names) if kb_names else "未知"
    return (
        "你是一名企业知识库的审核助理。下面是一篇等待人工审核的文档，"
        "以及系统在知识库中检索到的相似内容。请基于这些信息给出审核建议。\n\n"
        f"待审核文档标题：{title}\n\n"
        f"待审核文档正文：\n{content[:4000]}\n\n"
        f"系统检索到的相似文档片段：\n{ftext}\n\n"
        f"知识库列表（供你判断该文档最合适的归属）：{kb_list}\n\n"
        "请只输出一个 JSON 对象（不要使用 markdown 代码块，不要任何解释性文字），结构如下：\n"
        "{\n"
        '  "verdict": "approve" | "reject" | "manual_review",  // 建议：通过/驳回/人工复核\n'
        '  "summary": "一句话总结这篇文档的审核结论",\n'
        '  "duplicates": ["重复风险描述，如：与《XX》第N段高度重复(相似度0.9x)"],  // 无则空数组\n'
        '  "outdated_findings": ["过时信息描述，如：文中提及2024年费率，当前已2026年"],  // 无则空数组\n'
        '  "quality_notes": ["内容质量建议，如：缺少操作步骤/表述模糊"],  // 无则空数组\n'
        '  "suggested_kb": "最合适的知识库名称" 或 null  // 根据内容判断归属\n'
        "}\n"
    )


async def ai_review_document(
    kb_id: str,
    doc_id: str,
    db,
    embedder: EmbeddingModel,
    llm: OpenAICompatProvider,
) -> dict | None:
    """AI 辅助审核：相似度检索 + LLM 结构化建议。只读分析，不写库。

    流程：
      1) 拿待审文档 content_md，用现有 MarkdownChunker 切分
      2) 对分块做一次批量嵌入，与同库已审核文档的既有向量算余弦
         （相似度≥阈值则记为疑似重复，取 Top5）
      3) 把文档正文 + 相似发现 + 知识库列表喂给 LLM，产出结构化建议
    嵌入 API 偶发不可用时跳过相似度，仅走 LLM 定性分析，不阻断。
    """
    doc = await db.scalar(select(Document).where(Document.id == doc_id, Document.kb_id == kb_id))
    if not doc:
        return None

    content = doc.content_md or ""
    chunks = MarkdownChunker(
        settings.RAG_CHUNK_SIZE,
        settings.RAG_CHUNK_OVERLAP,
        settings.RAG_CHUNK_MIN_CHARS,
    ).chunk(content, doc.title)

    # ── 1. 相似度检索：拿已审核文档的既有向量与新文档向量算余弦 ──
    findings: list[dict] = []
    if chunks and content.strip():
        try:
            qvecs = np.array(await embedder.embed([c["content"] for c in chunks]), dtype=float)
        except Exception as e:  # 嵌入不可用则跳过相似度，仅走 LLM 定性
            qvecs = np.array([])
            print(f"[ai_review] embedding failed: {e}")
        if qvecs.size:
            existing = (
                await db.execute(
                    select(DocChunk, Document.title, Document.id)
                    .join(Document, Document.id == DocChunk.document_id)
                    .where(
                        DocChunk.kb_id == kb_id,
                        Document.status == "已审核",
                        Document.id != doc.id,
                    )
                )
            ).all()
            if existing:
                # 只保留有向量的 chunk；跳过 embedding 为 None 的记录，
                # 否则 np.array([None,...], dtype=float) 会塌成 1D，使 axis=1 的 norm 抛 AxisError。
                # 注意 existing 与向量数组必须一一对应，故同步过滤，避免 best_idx 错位。
                existing_f = [e for e in existing if e[0].embedding is not None]
                if existing_f:
                    try:
                        cvecs = np.array([e[0].embedding for e in existing_f], dtype=float)
                    except (ValueError, TypeError):
                        cvecs = np.array([])
                    # 必须是 2D 且非空（ragged / None 兜底为 1D 时跳过相似度）
                    if cvecs.ndim == 2 and cvecs.size:
                        # 零向量（演示数据）会除零 —— 加 1e-9 防 nan
                        qn = qvecs / (np.linalg.norm(qvecs, axis=1, keepdims=True) + 1e-9)
                        cn = cvecs / (np.linalg.norm(cvecs, axis=1, keepdims=True) + 1e-9)
                        sim = qn @ cn.T  # (新文档块数, 既有块数)
                        best_idx = np.argmax(sim, axis=1)
                        best_val = sim[np.arange(sim.shape[0]), best_idx]
                        by_doc: dict[str, dict] = {}
                        for i, val in enumerate(best_val):
                                if val < SIMILARITY_THRESHOLD:
                                    continue
                                ex = existing_f[int(best_idx[i])]
                                title = ex[1]
                                rec = by_doc.get(title)
                                if rec is None or val > rec["similarity"]:
                                    by_doc[title] = {
                                        "similarity": round(float(val), 3),
                                        "docTitle": title,
                                        "docId": str(ex[2]),
                                        "snippet": (ex[0].content[:160]).replace("\n", " "),
                                        "matchedChunk": (chunks[i]["content"][:120]).replace("\n", " "),
                                    }
                        findings = sorted(by_doc.values(), key=lambda x: x["similarity"], reverse=True)[:5]

    # ── 2. 知识库名称列表（供 LLM 判断归属） ──
    kb_rows = (await db.execute(select(KnowledgeBase.id, KnowledgeBase.name))).all()
    kb_names = [r.name for r in kb_rows]

    # ── 3. LLM 结构化建议 ──
    # AI 审核是辅助功能：LLM 接口一旦偶发报错（限流/超时/5xx），
    # 绝不能把整个请求 500 掉，否则前端拿不到任何分析。
    # 这里把 LLM 调用整体兜底，失败时降级为「人工复核」并保留已算出的相似度发现。
    messages = [
        {"role": "system", "content": "你是一名严谨的企业知识库审核助理，输出严格为 JSON。"},
        {"role": "user", "content": _build_review_prompt(doc.title, content, findings, kb_names)},
    ]
    try:
        raw = await llm.chat(messages)
        parsed = OpenAICompatProvider._extract_json(raw)
        verdict = parsed.get("verdict") or "manual_review"
        summary = (parsed.get("summary") or "").strip()
        duplicates = parsed.get("duplicates") or []
        outdated_findings = parsed.get("outdated_findings") or []
        quality_notes = parsed.get("quality_notes") or []
        suggested_kb = parsed.get("suggested_kb") or None
    except Exception as e:  # LLM 不可用 → 降级，不阻断审核流程
        print(f"[ai_review] LLM 调用失败，降级为人工复核: {e}")
        verdict = "manual_review"
        summary = "AI 分析服务暂时不可用，已降级为人工复核，请人工判断。"
        duplicates = []
        outdated_findings = []
        quality_notes = []
        suggested_kb = None

    return {
        "verdict": verdict,
        "summary": summary,
        "duplicates": duplicates,
        "outdated_findings": outdated_findings,
        "quality_notes": quality_notes,
        "suggested_kb": suggested_kb,
        "similarity_findings": findings,
    }
