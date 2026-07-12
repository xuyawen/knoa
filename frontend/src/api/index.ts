import type {
  KnowledgeBasesResponse,
  SSEEvent,
  TrendingItem,
  DocumentItem,
  SourceDetail,
} from '@/types/api'

export async function getKnowledgeBases(): Promise<KnowledgeBasesResponse> {
  const resp = await fetch('/api/knowledge-bases')
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

export async function getTrending(): Promise<TrendingItem[]> {
  const resp = await fetch('/api/trending')
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 列出某知识库下的文档。 */
export async function getDocuments(kbId: string): Promise<DocumentItem[]> {
  const resp = await fetch(`/api/knowledge-bases/${kbId}/documents`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 上传单篇文档（.md / .txt）。前端用 FileReader 读文本后提交。 */
export async function uploadDocument(
  kbId: string,
  filename: string,
  content: string,
): Promise<DocumentItem> {
  const resp = await fetch(`/api/knowledge-bases/${kbId}/documents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, content }),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** 溯源详情：按 chunk 的 UUID 取原文。 */
export async function getSourceDetail(chunkId: string): Promise<SourceDetail> {
  const resp = await fetch(`/api/sources/${chunkId}`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 提交/更新对某条回答的反馈（👍/👎）。 */
export async function submitFeedback(messageId: string, rating: 'up' | 'down') {
  const resp = await fetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messageId, rating }),
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 取消对某条回答的反馈。 */
export async function deleteFeedback(messageId: string) {
  const resp = await fetch(`/api/feedback/${messageId}`, { method: 'DELETE' })
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
  opts?: { timeoutMs?: number },
): AsyncGenerator<SSEEvent> {
  // 客户端超时保护：Agentic RAG 多步决策链可能需要多次 LLM 调用（每轮 15~40s），
  // 90s 对复杂问题不够用，拉到 180s 给足余量
  const controller = new AbortController()
  const timeoutMs = opts?.timeoutMs ?? 180_000
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const resp = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, knowledgeBase, sessionId }),
      signal: controller.signal,
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
    if (controller.signal.aborted) {
      yield { event: 'error', data: { message: '请求超时，请稍后重试' } }
    } else {
      const msg = e instanceof Error ? e.message : String(e)
      yield { event: 'error', data: { message: `网络错误：${msg}` } }
    }
  } finally {
    clearTimeout(timer)
  }
}
