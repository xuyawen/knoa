import type {
  KnowledgeBasesResponse,
  SSEEvent,
  TrendingItem,
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
  // 客户端超时保护：防止后端挂起导致 UI 永远转圈
  const controller = new AbortController()
  const timeoutMs = opts?.timeoutMs ?? 90_000
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
      buffer += decoder.decode(value, { stream: true })

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
