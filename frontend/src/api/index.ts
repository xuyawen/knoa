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
  GraphData,
  GraphFilter,
  GraphHotNode,
  GraphNode,
  DashboardMetrics,
  TrendResponse,
  DocCategory,
  OperationsResponse,
  Announcement,
  AnnouncementCreate,
  AnnouncementUpdate,
  Settings,
  SettingsUpdate,
  TtsResult,
  DocStats,
  UserStats,
  HotQueryItem,
  DepartmentNode,
  DocumentTaskOut,
  DocumentList,
  Paginated,
  SearchDocsResponse,
} from '@/types/api'
import { authHeaders, TokenExpiredError } from './http'

export async function getKnowledgeBases(
  page = 1,
  size = 20,
): Promise<KnowledgeBasesResponse> {
  const resp = await fetch(`/api/knowledge-bases?page=${page}&size=${size}`, { headers: authHeaders() })
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

/** 全局文档搜索（智能搜索页文档结果列表）。 */
export async function searchDocs(
  q: string,
  opts?: { page?: number; size?: number; type?: string; scope?: string; category?: string; status?: string; time?: string },
): Promise<SearchDocsResponse> {
  const params = new URLSearchParams()
  params.set('q', q)
  if (opts?.page) params.set('page', String(opts.page))
  if (opts?.size) params.set('size', String(opts.size))
  if (opts?.type) params.set('doc_type', opts.type)
  if (opts?.scope) params.set('scope', opts.scope)
  if (opts?.category) params.set('category', opts.category)
  if (opts?.status) params.set('status', opts.status)
  if (opts?.time) params.set('updated_after', opts.time)
  const resp = await fetch(`/api/search/docs?${params.toString()}`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 列出某知识库下的文档（服务端分页 + 真实过滤）。 */
export async function getDocuments(
  kbId: string,
  opts?: { page?: number; size?: number; scope?: string; type?: string; status?: string; q?: string; mine?: boolean; departmentId?: string; tags?: string },
): Promise<DocumentList> {
  const params = new URLSearchParams()
  if (opts?.page) params.set('page', String(opts.page))
  if (opts?.size) params.set('size', String(opts.size))
  if (opts?.scope) params.set('scope', opts.scope)
  if (opts?.type) params.set('type', opts.type)
  if (opts?.status) params.set('status', opts.status)
  if (opts?.q) params.set('q', opts.q)
  if (opts?.mine) params.set('mine', 'true')
  if (opts?.departmentId) params.set('department_id', opts.departmentId)
  if (opts?.tags) params.set('tags', opts.tags)
  const qs = params.toString()
  const resp = await fetch(`/api/knowledge-bases/${kbId}/documents${qs ? `?${qs}` : ''}`, { headers: authHeaders() })
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

/** 会话列表（分页）。 */
export async function getSessions(
  page = 1,
  size = 20,
): Promise<Paginated<ChatSession>> {
  const resp = await fetch(`/api/sessions?page=${page}&size=${size}`, { headers: authHeaders() })
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

/** 知识图谱只读数据：返回 kg_node / kg_edge 的真实节点与边（支持筛选）。 */
export async function getGraph(kbId?: string | null, filter?: GraphFilter): Promise<GraphData> {
  const params = new URLSearchParams()
  if (kbId) params.set('kb_id', kbId)
  if (filter?.nodeType) params.set('node_type', filter.nodeType)
  if (filter?.bizCategory) params.set('biz_category', filter.bizCategory)
  if (filter?.from) params.set('from', filter.from)
  if (filter?.to) params.set('to', filter.to)
  const qs = params.toString()
  const resp = await fetch(`/api/graph${qs ? `?${qs}` : ''}`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 热门实体 TopN（按度数）。 */
export async function getGraphHotNodes(limit = 5, kbId?: string | null): Promise<GraphHotNode[]> {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  if (kbId) params.set('kb_id', kbId)
  const resp = await fetch(`/api/graph/hot-nodes?${params.toString()}`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 最近更新实体 TopN（按 created_at）。 */
export async function getGraphRecent(limit = 5, kbId?: string | null): Promise<GraphNode[]> {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  if (kbId) params.set('kb_id', kbId)
  const resp = await fetch(`/api/graph/recent?${params.toString()}`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 导出完整图谱（json / gexf），触发浏览器下载。 */
export async function exportGraph(format: 'json' | 'gexf' = 'json', kbId?: string | null): Promise<void> {
  const params = new URLSearchParams()
  params.set('format', format)
  if (kbId) params.set('kb_id', kbId)
  const resp = await fetch(`/api/graph/export?${params.toString()}`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = format === 'gexf' ? 'graph.gexf' : 'graph.json'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
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
  opts?: { timeoutMs?: number; signal?: AbortSignal; mode?: string },
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
      body: JSON.stringify({ question, knowledgeBase, sessionId, files: files ?? [], mode: opts?.mode ?? 'chat' }),
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
        // SSE 规范：缺省 event 类型即 'message'。原先要求 eventType 非空会把这类
        // 事件静默丢弃，改为回退到 'message'，与 SSEEvent 联合类型保持一致。
        if (dataStr) {
          try {
            yield { event: eventType || 'message', data: JSON.parse(dataStr) } as SSEEvent
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

/* ===== Phase 1 业务统计 ===== */

/** Dashboard 核心指标 + 日环比（真实数据源：operation_log / document）。 */
export async function getDashboardMetrics(): Promise<DashboardMetrics> {
  const resp = await fetch('/api/analytics/dashboard', { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 问答趋势（按时间桶聚合，range: today | week | month）。 */
export async function getTrend(range: 'today' | 'week' | 'month' = 'week'): Promise<TrendResponse> {
  const resp = await fetch(`/api/analytics/trend?range=${range}`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 文档分类占比（饼图数据源）。 */
export async function getDocCategory(): Promise<DocCategory[]> {
  const resp = await fetch('/api/analytics/doc-category', { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 用户统计：活跃/总用户/新增/角色/状态/近7天趋势（用户统计分区）。 */
export async function getUserStats(): Promise<UserStats> {
  const resp = await fetch('/api/analytics/user-stats', { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 文档统计：按 category / status 聚合（文档统计分区）。 */
export async function getDocStats(): Promise<DocStats> {
  const resp = await fetch('/api/analytics/doc-stats', { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 操作日志分页列表（仅 admin）。 */
export async function getOperations(page = 1, size = 20): Promise<OperationsResponse> {
  const resp = await fetch(`/api/operations?page=${page}&size=${size}`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 公告列表（所有登录用户可见，分页）。 */
export async function getAnnouncements(
  page = 1,
  size = 20,
): Promise<Paginated<Announcement>> {
  const resp = await fetch(`/api/announcements?page=${page}&size=${size}`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 新建公告（仅 admin）。 */
export async function createAnnouncement(payload: AnnouncementCreate): Promise<Announcement> {
  const resp = await fetch('/api/announcements', {
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

/** 更新公告（仅 admin）。 */
export async function updateAnnouncement(
  id: string,
  payload: AnnouncementUpdate,
): Promise<Announcement> {
  const resp = await fetch(`/api/announcements/${id}`, {
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

/** 删除公告（仅 admin）。 */
export async function deleteAnnouncement(id: string): Promise<void> {
  const resp = await fetch(`/api/announcements/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
}

/** 标记某公告为已读（幂等 upsert）。P8 通知中心使用。 */
export async function markAnnouncementRead(id: string): Promise<void> {
  const resp = await fetch(`/api/announcements/${id}/read`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
}

/** 热门问答榜（近 30 天 action=ask 聚合 Top 10）。 */
export async function getHotAsk(): Promise<HotQueryItem[]> {
  const resp = await fetch('/api/analytics/hot-ask', { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 知识缺口榜（近 30 天零检索命中的提问聚合 Top 10）。 */
export async function getKnowledgeGaps(): Promise<HotQueryItem[]> {
  const resp = await fetch('/api/analytics/knowledge-gaps', { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 读取个人系统设置（preferredModel / ttsEnabled）。P8 新增。 */
export async function getSettings(): Promise<Settings> {
  const resp = await fetch('/api/settings', { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 更新个人系统设置。P8 新增。 */
export async function updateSettings(payload: SettingsUpdate): Promise<Settings> {
  const resp = await fetch('/api/settings', {
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

/** 文本转语音：返回 base64 音频 + contentType。前端拼 data URI 播放。P8 新增。 */
export async function ttsSpeak(text: string): Promise<TtsResult> {
  const resp = await fetch('/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ text }),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** 部门树（嵌套）。P5 部门筛选使用。 */
export async function getDepartments(): Promise<DepartmentNode[]> {
  const resp = await fetch(`/api/departments`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 某知识库文档去重标签枚举。P5 标签筛选下拉使用。 */
export async function getDocumentTags(kbId: string): Promise<string[]> {
  const resp = await fetch(`/api/knowledge-bases/${kbId}/tags`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 轮询单个文档处理任务进度（P5 上传进度条）。 */
export async function getDocumentTask(taskId: string): Promise<DocumentTaskOut> {
  const resp = await fetch(`/api/documents/tasks/${taskId}`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 按 document_id 查任务列表（取最新一条拿到 task id，分页）。 */
export async function getDocumentTasks(
  documentId: string,
  page = 1,
  size = 20,
): Promise<Paginated<DocumentTaskOut>> {
  const resp = await fetch(`/api/documents/tasks?document_id=${documentId}&page=${page}&size=${size}`, { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}
