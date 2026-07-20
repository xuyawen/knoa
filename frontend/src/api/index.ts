import type {
  KnowledgeBasesResponse,
  SSEEvent,
  TrendingItem,
  DocumentItem,
  DocumentDetail,
  SourceDetail,
  ChatSession,
  SessionDetail,
  KBUpdate,
  KnowledgeBase,
  AIReview,
  ChatAttachment,
} from '@/types/api'
import { authHeaders, TokenExpiredError } from './http'

export async function getKnowledgeBases(): Promise<KnowledgeBasesResponse> {
  const resp = await fetch('/api/knowledge-bases', { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 新建知识库（菜单级库：合规管理 / 广告运营 …）。 */
export async function createKnowledgeBase(payload: {
  name: string
  icon?: string | null
  description?: string | null
}): Promise<{ id: string; name: string; icon: string }> {
  const resp = await fetch('/api/knowledge-bases', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

export async function getTrending(): Promise<TrendingItem[]> {
  const resp = await fetch('/api/trending', { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 列出某知识库下的文档。 */
export async function getDocuments(kbId: string): Promise<DocumentItem[]> {
  const resp = await fetch(`/api/knowledge-bases/${kbId}/documents`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 上传单篇文档（.md / .txt / .docx / .pdf）。
 *  前端把文件读成 base64 原始字节（contentB64）提交，后端按扩展名解析。 */
export async function uploadDocument(
  kbId: string,
  filename: string,
  contentB64: string,
): Promise<DocumentItem> {
  const resp = await fetch(`/api/knowledge-bases/${kbId}/documents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ filename, contentB64 }),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** 文档详情：返回解析后的全文（contentMd）。 */
export async function getDocument(kbId: string, docId: string): Promise<DocumentDetail> {
  const resp = await fetch(`/api/knowledge-bases/${kbId}/documents/${docId}`, {
    headers: authHeaders(),
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 审核通过：触发摄入，文档进入检索库。 */
export async function approveDocument(kbId: string, docId: string): Promise<DocumentItem> {
  const resp = await fetch(`/api/knowledge-bases/${kbId}/documents/${docId}/approve`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** 审核驳回：状态改为已拒绝，不摄入。 */
export async function rejectDocument(kbId: string, docId: string): Promise<DocumentItem> {
  const resp = await fetch(`/api/knowledge-bases/${kbId}/documents/${docId}/reject`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** 删除文档：级联清理 chunk / ES / 图谱 / 对象存储。 */
export async function deleteDocument(kbId: string, docId: string): Promise<void> {
  const resp = await fetch(`/api/knowledge-bases/${kbId}/documents/${docId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
}

/** AI 辅助审核文档。 */
export async function aiReviewDocument(
  kbId: string,
  docId: string,
): Promise<AIReview> {
  const resp = await fetch(`/api/knowledge-bases/${kbId}/documents/${docId}/ai-review`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** 溯源详情：按 chunk 的 UUID 取原文。 */
export async function getSourceDetail(chunkId: string): Promise<SourceDetail> {
  const resp = await fetch(`/api/sources/${chunkId}`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 会话列表。 */
export async function getSessions(): Promise<ChatSession[]> {
  const resp = await fetch('/api/sessions', { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 新建空会话，返回 id。 */
export async function createSession(): Promise<ChatSession> {
  const resp = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ title: null }),
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 拉取某会话的全部消息。 */
export async function getSession(id: string): Promise<SessionDetail> {
  const resp = await fetch(`/api/sessions/${id}`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 删除单个会话（级联删除消息）。 */
export async function deleteSession(id: string): Promise<void> {
  const resp = await fetch(`/api/sessions/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
}

/** 批量删除会话。 */
export async function batchDeleteSessions(ids: string[]): Promise<void> {
  const resp = await fetch('/api/sessions/batch-delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ ids }),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
}

/** 提交/更新对某条回答的反馈（👍/👎）。 */
export async function submitFeedback(messageId: string, rating: 'up' | 'down') {
  const resp = await fetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ messageId, rating }),
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 编辑知识库：只传需改字段（name / icon / description）。 */
export async function updateKnowledgeBase(
  id: string,
  payload: KBUpdate,
): Promise<KnowledgeBase> {
  const resp = await fetch(`/api/knowledge-bases/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** 删除单个知识库（级联清理其下文档 / 向量 / 图谱）。 */
export async function deleteKnowledgeBase(id: string): Promise<void> {
  const resp = await fetch(`/api/knowledge-bases/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
}

/** 拖拽排序：传回当前完整 id 顺序，后端按下标赋 order。 */
export async function reorderKnowledgeBases(orderedIds: string[]): Promise<void> {
  const resp = await fetch('/api/knowledge-bases/reorder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ orderedIds }),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
}

/** 批量删除知识库。 */
export async function batchDeleteKnowledgeBases(ids: string[]): Promise<void> {
  const resp = await fetch('/api/knowledge-bases/batch-delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ ids }),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
}

/** 取消对某条回答的反馈。 */
export async function deleteFeedback(messageId: string) {
  const resp = await fetch(`/api/feedback/${messageId}`, { method: 'DELETE', headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/**
 * SSE 流式问答。POST /api/ask -> text/event-stream
 * 因为是 POST, 不能用 EventSource, 用 fetch + ReadableStream 手动解析
 */
export async function* streamAsk(
  question: string,
  knowledgeBase?: string | null,
  sessionId?: string | null,
  files?: ChatAttachment[],
  opts?: { timeoutMs?: number; signal?: AbortSignal },
): AsyncGenerator<SSEEvent> {
  // 客户端超时保护：Agentic RAG 多步决策链可能需要多次 LLM 调用（每轮 15~40s），
  // 90s 对复杂问题不够用，拉到 180s 给足余量
  const ac = new AbortController()
  const timeoutMs = opts?.timeoutMs ?? 180_000
  let timedOut = false
  // 外部主动取消（切会话 / 新建会话）通过 signal 透传，复用同一个 ac 中断 fetch
  const onExternalAbort = () => ac.abort()
  if (opts?.signal) opts.signal.addEventListener('abort', onExternalAbort)
  const timer = setTimeout(() => {
    timedOut = true
    ac.abort()
  }, timeoutMs)

  try {
    const resp = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ question, knowledgeBase, sessionId, files: files ?? [] }),
      signal: ac.signal,
    })

    if (!resp.ok || !resp.body) {
      const text = await resp.text().catch(() => '')
      yield { event: 'error', data: { message: `HTTP ${resp.status}: ${text}` } }
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      // FastAPI / sse-starlette emits CRLF (\r\n) line endings; normalize to LF
      // so we can split events on "\n\n" regardless of the backend's line style.
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')

      const events = buffer.split('\n\n')
      buffer = events.pop() || ''

      for (const raw of events) {
        const lines = raw.split('\n')
        let eventType = ''
        let dataStr = ''
        for (const line of lines) {
          if (line.startsWith('event:')) eventType = line.slice(6).trim()
          else if (line.startsWith('data:')) dataStr += line.slice(5).trim()
        }
        if (eventType && dataStr) {
          try {
            yield { event: eventType, data: JSON.parse(dataStr) } as SSEEvent
          } catch {
            // skip malformed
          }
        }
      }
    }
  } catch (e: unknown) {
    if (e instanceof TokenExpiredError) {
      // 身份失效由全局弹窗统一处理，流直接结束，不追加错误文案
      return
    }
    if (ac.signal.aborted) {
      // 主动取消（切会话 / 新建会话）不提示；仅超时给文案
      if (timedOut) yield { event: 'error', data: { message: '请求超时，请稍后重试' } }
      return
    }
    const msg = e instanceof Error ? e.message : String(e)
    yield { event: 'error', data: { message: `网络错误：${msg}` } }
  } finally {
    if (opts?.signal) opts.signal.removeEventListener('abort', onExternalAbort)
    clearTimeout(timer)
  }
}
