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
  DepartmentOut,
  DepartmentCreateIn,
  DepartmentUpdateIn,
  DocumentTaskOut,
  DocumentList,
  Paginated,
  SearchDocsResponse,
  RecordsResponse,
  KBMember,
  KBMembersUpdate,
  MemoryItem,
} from '@/types/api'
import { TokenExpiredError, request, requestVoid, requestRaw } from './http'
import { report } from '../lib/monitor'

export async function getKnowledgeBases(
  page = 1,
  size = 20,
): Promise<KnowledgeBasesResponse> {
  return request(`/api/knowledge-bases?page=${page}&size=${size}`)
}

/** 新建知识库（菜单级库：合规管理 / 广告运营 …）。 */
export async function createKnowledgeBase(payload: {
  name: string
  icon?: string | null
  description?: string | null
}): Promise<{ id: string; name: string; icon: string }> {
  return request('/api/knowledge-bases', { method: 'POST', json: payload })
}

/** 列出某知识库成员（库 admin 或全局 admin）。 */
export async function getKbMembers(kbId: string): Promise<KBMember[]> {
  const data = await request<{ members: KBMember[] }>(`/api/knowledge-bases/${kbId}/members`)
  return data.members
}

/** 全量设置某知识库成员（覆盖式）。 */
export async function setKbMembers(kbId: string, payload: KBMembersUpdate): Promise<KBMember[]> {
  const data = await request<{ members: KBMember[] }>(`/api/knowledge-bases/${kbId}/members`, {
    method: 'PUT',
    json: payload,
  })
  return data.members
}

/** 列出当前用户全部长期记忆（按时间倒序）。 */
export async function getMemories(): Promise<MemoryItem[]> {
  const data = await request<{ memories: MemoryItem[] }>('/api/memories')
  return data.memories
}

/** 删除一条记忆。 */
export async function deleteMemory(id: string): Promise<void> {
  await requestVoid(`/api/memories/${id}`, { method: 'DELETE' })
}

/** 清空当前用户全部记忆。 */
export async function clearMemories(): Promise<number> {
  const data = await request<{ deleted?: number }>('/api/memories', { method: 'DELETE' })
  return data.deleted ?? 0
}

export async function getTrending(): Promise<TrendingItem[]> {
  return request('/api/trending')
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
  return request(`/api/search/docs?${params.toString()}`)
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
  return request(`/api/knowledge-bases/${kbId}/documents${qs ? `?${qs}` : ''}`)
}

/** 上传单篇文档（.md / .txt / .docx / .pdf）。
 *  两种提交方式（互斥，优先 fileUrl）：
 *   - fileUrl：前端已直传 OSS，只回传可访问地址，后端按 URL 回抓字节解析
 *   - contentB64：旧流程，前端把文件读成 base64 原始字节提交 */
export async function uploadDocument(
  kbId: string,
  filename: string,
  opts?: { contentB64?: string; fileUrl?: string },
): Promise<DocumentItem> {
  const body: Record<string, unknown> = { filename }
  if (opts?.fileUrl) body.fileUrl = opts.fileUrl
  else if (opts?.contentB64) body.contentB64 = opts.contentB64
  return request(`/api/knowledge-bases/${kbId}/documents`, { method: 'POST', json: body })
}

/** 获取 OSS PostObject 直传签名（空前端凭此直传，AccessKey 不落浏览器）。 */
export async function getOssSign(prefix: string, filename: string): Promise<{
  accessKeyId: string
  policy: string
  signature: string
  host: string
  key: string
  url: string
  expiresAt: number
}> {
  return request('/api/oss/sign', { method: 'POST', json: { prefix, filename } })
}

/** 文档详情：返回解析后的全文（contentMd）。 */
export async function getDocument(kbId: string, docId: string): Promise<DocumentDetail> {
  return request(`/api/knowledge-bases/${kbId}/documents/${docId}`)
}

/** 按文档 id 直接取详情（操作审计/问答溯源点击预览用，无需已知 kbId）。 */
export async function getDocumentById(docId: string): Promise<DocumentDetail> {
  return request(`/api/documents/${docId}`)
}

/** 审核通过：触发摄入，文档进入检索库。 */
export async function approveDocument(kbId: string, docId: string): Promise<DocumentItem> {
  return request(`/api/knowledge-bases/${kbId}/documents/${docId}/approve`, { method: 'POST' })
}

/** 审核驳回：状态改为已拒绝，不摄入。 */
export async function rejectDocument(kbId: string, docId: string): Promise<DocumentItem> {
  return request(`/api/knowledge-bases/${kbId}/documents/${docId}/reject`, { method: 'POST' })
}

/** 删除文档：级联清理 chunk / ES / 图谱 / 对象存储。 */
export async function deleteDocument(kbId: string, docId: string): Promise<void> {
  await requestVoid(`/api/knowledge-bases/${kbId}/documents/${docId}`, { method: 'DELETE' })
}

/** AI 辅助审核文档。 */
export async function aiReviewDocument(
  kbId: string,
  docId: string,
): Promise<AIReview> {
  return request(`/api/knowledge-bases/${kbId}/documents/${docId}/ai-review`, { method: 'POST' })
}

/** 溯源详情：按 chunk 的 UUID 取原文。 */
export async function getSourceDetail(chunkId: string): Promise<SourceDetail> {
  return request(`/api/sources/${chunkId}`)
}

/** 会话列表（分页）。 */
export async function getSessions(
  page = 1,
  size = 20,
): Promise<Paginated<ChatSession>> {
  return request(`/api/sessions?page=${page}&size=${size}`)
}

/** 检索记录分页（服务端分页 + 来源类型过滤）。 */
export async function getRecords(
  opts?: { page?: number; size?: number; filter?: string },
): Promise<RecordsResponse> {
  const params = new URLSearchParams()
  if (opts?.page) params.set('page', String(opts.page))
  if (opts?.size) params.set('size', String(opts.size))
  if (opts?.filter) params.set('f', opts.filter)
  const qs = params.toString()
  return request(`/api/records${qs ? `?${qs}` : ''}`)
}

/** 新建空会话，返回 id。 */
export async function createSession(): Promise<ChatSession> {
  return request('/api/sessions', { method: 'POST', json: { title: null } })
}

/** 拉取某会话的全部消息。 */
export async function getSession(id: string): Promise<SessionDetail> {
  return request(`/api/sessions/${id}`)
}

/** 删除单个会话（级联删除消息）。 */
export async function deleteSession(id: string): Promise<void> {
  await requestVoid(`/api/sessions/${id}`, { method: 'DELETE' })
}

/** 清空会话全部消息（保留会话壳，后端同时重置滚动摘要边界）。 */
export async function clearSessionMessages(id: string): Promise<void> {
  await requestVoid(`/api/sessions/${id}/messages`, { method: 'DELETE' })
}

/** 重命名会话。 */
export async function renameSession(id: string, title: string): Promise<{ ok: boolean; title: string }> {
  return request(`/api/sessions/${id}`, { method: 'PATCH', json: { title } })
}

/** 删除单条消息（「重新生成」先移除旧回答再重问）。 */
export async function deleteMessage(messageId: string): Promise<void> {
  await requestVoid(`/api/messages/${messageId}`, { method: 'DELETE' })
}

/** 批量删除会话。 */
export async function batchDeleteSessions(ids: string[]): Promise<void> {
  await requestVoid('/api/sessions/batch-delete', { method: 'POST', json: { ids } })
}

/** 提交/更新对某条回答的反馈（👍/👎）。 */
export async function submitFeedback(messageId: string, rating: 'up' | 'down') {
  return request<unknown>('/api/feedback', { method: 'POST', json: { messageId, rating } })
}

/** 编辑知识库：只传需改字段（name / icon / description）。 */
export async function updateKnowledgeBase(
  id: string,
  payload: KBUpdate,
): Promise<KnowledgeBase> {
  return request(`/api/knowledge-bases/${id}`, { method: 'PUT', json: payload })
}

/** 删除单个知识库（级联清理其下文档 / 向量 / 图谱）。 */
export async function deleteKnowledgeBase(id: string): Promise<void> {
  await requestVoid(`/api/knowledge-bases/${id}`, { method: 'DELETE' })
}

/** 拖拽排序：传回当前完整 id 顺序，后端按下标赋 order。 */
export async function reorderKnowledgeBases(orderedIds: string[]): Promise<void> {
  await requestVoid('/api/knowledge-bases/reorder', { method: 'POST', json: { orderedIds } })
}

/** 批量删除知识库。 */
export async function batchDeleteKnowledgeBases(ids: string[]): Promise<void> {
  await requestVoid('/api/knowledge-bases/batch-delete', { method: 'POST', json: { ids } })
}

/** 取消对某条回答的反馈。 */
export async function deleteFeedback(messageId: string) {
  return request<unknown>(`/api/feedback/${messageId}`, { method: 'DELETE' })
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
  return request(`/api/graph${qs ? `?${qs}` : ''}`)
}

/** 热门实体 TopN（按度数）。 */
export async function getGraphHotNodes(limit = 5, kbId?: string | null): Promise<GraphHotNode[]> {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  if (kbId) params.set('kb_id', kbId)
  return request(`/api/graph/hot-nodes?${params.toString()}`)
}

/** 最近更新实体 TopN（按 created_at）。 */
export async function getGraphRecent(limit = 5, kbId?: string | null): Promise<GraphNode[]> {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  if (kbId) params.set('kb_id', kbId)
  return request(`/api/graph/recent?${params.toString()}`)
}

/** 导出完整图谱（json / gexf），触发浏览器下载。 */
export async function exportGraph(format: 'json' | 'gexf' = 'json', kbId?: string | null): Promise<void> {
  const params = new URLSearchParams()
  params.set('fmt', format) // 后端参数名是 fmt（避开 format 保留字），传错会被静默忽略
  if (kbId) params.set('kb_id', kbId)
  const resp = await requestRaw(`/api/graph/export?${params.toString()}`)
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
 * （需要逐块读响应流，不走 request<T> 封装）
 */
export async function* streamAsk(
  question: string,
  knowledgeBase?: string | null,
  sessionId?: string | null,
  files?: ChatAttachment[],
  opts?: {
    timeoutMs?: number
    signal?: AbortSignal
    mode?: string
    modelConfig?: Record<string, unknown> | null  // ModelConfig 页下发的配置，随 ask 请求带去后端
  },
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
    const body: Record<string, unknown> = {
      question,
      knowledgeBase,
      sessionId,
      files: files ?? [],
      mode: opts?.mode ?? 'chat',
    }
    // 把模型配置摊平进请求体（后端 AskRequest 对应字段，空值不传以走后端默认）
    if (opts?.modelConfig) {
      for (const [k, v] of Object.entries(opts.modelConfig)) {
        if (v !== null && v !== undefined && v !== '') body[k] = v
      }
    }
    const resp = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ac.signal,
    })

    if (!resp.ok || !resp.body) {
      // 不要把后端原始响应体回显给用户（可能含内部信息）；仅展示通用文案，
      // 原始信息走 report() 便于排查。
      const text = await resp.text().catch(() => '')
      report({ type: 'ask.http_error', message: `${resp.status}: ${text}`, level: 'error' })
      yield { event: 'error', data: { message: '请求失败，请稍后重试' } }
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
  return request('/api/analytics/dashboard')
}

/** 问答趋势（按时间桶聚合，range: today | week | month）。 */
export async function getTrend(range: 'today' | 'week' | 'month' = 'week'): Promise<TrendResponse> {
  return request(`/api/analytics/trend?range=${range}`)
}

/** 文档分类占比（饼图数据源）。 */
export async function getDocCategory(): Promise<DocCategory[]> {
  return request('/api/analytics/doc-category')
}

/** 用户统计：活跃/总用户/新增/角色/状态/近7天趋势（用户统计分区）。 */
export async function getUserStats(): Promise<UserStats> {
  return request('/api/analytics/user-stats')
}

/** 文档统计：按 category / status 聚合（文档统计分区）。 */
export async function getDocStats(): Promise<DocStats> {
  return request('/api/analytics/doc-stats')
}

/** 操作日志分页列表（仅 admin）。 */
export async function getOperations(page = 1, size = 20): Promise<OperationsResponse> {
  return request(`/api/operations?page=${page}&size=${size}`)
}

/** 公告列表（所有登录用户可见，分页）。 */
export async function getAnnouncements(
  page = 1,
  size = 20,
): Promise<Paginated<Announcement>> {
  return request(`/api/announcements?page=${page}&size=${size}`)
}

/** 新建公告（仅 admin）。 */
export async function createAnnouncement(payload: AnnouncementCreate): Promise<Announcement> {
  return request('/api/announcements', { method: 'POST', json: payload })
}

/** 更新公告（仅 admin）。 */
export async function updateAnnouncement(
  id: string,
  payload: AnnouncementUpdate,
): Promise<Announcement> {
  return request(`/api/announcements/${id}`, { method: 'PUT', json: payload })
}

/** 删除公告（仅 admin）。 */
export async function deleteAnnouncement(id: string): Promise<void> {
  await requestVoid(`/api/announcements/${id}`, { method: 'DELETE' })
}

/** 标记某公告为已读（幂等 upsert）。P8 通知中心使用。 */
export async function markAnnouncementRead(id: string): Promise<void> {
  await requestVoid(`/api/announcements/${id}/read`, { method: 'POST' })
}

/** 热门问答榜（近 30 天 action=ask 聚合 Top 10）。 */
export async function getHotAsk(): Promise<HotQueryItem[]> {
  return request('/api/analytics/hot-ask')
}

/** 知识缺口榜（近 30 天零检索命中的提问聚合 Top 10）。 */
export async function getKnowledgeGaps(): Promise<HotQueryItem[]> {
  return request('/api/analytics/knowledge-gaps')
}

/* ---------- 字典类接口缓存（P4）----------
 * 低频变化数据（部门树 / 个人设置）被多视图重复拉取：
 * 模块级 promise 缓存做 in-flight 去重 + TTL，写接口成功后主动失效。 */
const _dictCache = new Map<string, { at: number; p: Promise<unknown> }>()
const DICT_TTL_MS = 60_000

function cachedDict<T>(key: string, loader: () => Promise<T>): Promise<T> {
  const hit = _dictCache.get(key)
  if (hit && Date.now() - hit.at < DICT_TTL_MS) return hit.p as Promise<T>
  const p = loader().catch((e) => {
    // 失败不缓存，下次调用重新请求
    _dictCache.delete(key)
    throw e
  })
  _dictCache.set(key, { at: Date.now(), p })
  return p
}

function invalidateDict(key: string) {
  _dictCache.delete(key)
}

/** 读取个人系统设置（preferredModel / ttsEnabled）。P8 新增；带 60s 缓存。 */
export async function getSettings(): Promise<Settings> {
  return cachedDict('settings', () => request<Settings>('/api/settings'))
}

/** 更新个人系统设置。P8 新增；成功后失效设置缓存。 */
export async function updateSettings(payload: SettingsUpdate): Promise<Settings> {
  const data = await request<Settings>('/api/settings', { method: 'PUT', json: payload })
  invalidateDict('settings')
  return data
}

/** 文本转语音：返回 base64 音频 + contentType。前端拼 data URI 播放。P8 新增。 */
export async function ttsSpeak(text: string, voiceType?: number): Promise<TtsResult> {
  return request('/api/tts', { method: 'POST', json: { text, voiceType: voiceType ?? null } })
}

/** 部门树（嵌套）。P5 部门筛选使用；带 60s 缓存 + in-flight 去重。 */
export async function getDepartments(): Promise<DepartmentNode[]> {
  return cachedDict('departments', () => request<DepartmentNode[]>('/api/departments'))
}

/** 新建部门（仅 admin）。成功后失效部门树缓存。 */
export async function createDepartment(payload: DepartmentCreateIn): Promise<DepartmentOut> {
  const data = await request<DepartmentOut>('/api/departments', { method: 'POST', json: payload })
  invalidateDict('departments')
  return data
}

/** 更新部门（仅 admin）。成功后失效部门树缓存。 */
export async function updateDepartment(id: string, payload: DepartmentUpdateIn): Promise<DepartmentOut> {
  const data = await request<DepartmentOut>(`/api/departments/${id}`, { method: 'PATCH', json: payload })
  invalidateDict('departments')
  return data
}

/** 删除部门（仅 admin；有子部门或关联文档时后端阻止）。成功后失效部门树缓存。 */
export async function deleteDepartment(id: string): Promise<void> {
  await requestVoid(`/api/departments/${id}`, { method: 'DELETE' })
  invalidateDict('departments')
}

/** 某知识库文档去重标签枚举。P5 标签筛选下拉使用。 */
export async function getDocumentTags(kbId: string): Promise<string[]> {
  return request(`/api/knowledge-bases/${kbId}/tags`)
}

/** 轮询单个文档处理任务进度（P5 上传进度条）。 */
export async function getDocumentTask(taskId: string): Promise<DocumentTaskOut> {
  return request(`/api/documents/tasks/${taskId}`)
}

/** 按 document_id 查任务列表（取最新一条拿到 task id，分页）。 */
export async function getDocumentTasks(
  documentId: string,
  page = 1,
  size = 20,
): Promise<Paginated<DocumentTaskOut>> {
  return request(`/api/documents/tasks?document_id=${documentId}&page=${page}&size=${size}`)
}
