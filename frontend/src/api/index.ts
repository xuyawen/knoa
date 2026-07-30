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
  GraphMergePreview,
  GraphMergeRequest,
  GraphMergeResult,
  GraphNode,
  GraphNodeListQuery,
  GraphNodeListResult,
  GraphEdgeListQuery,
  GraphEdgeListResult,
  GraphNodeSource,
  KGGapSignal,
  DashboardMetrics,
  TrendResponse,
  KbDistribution,
  OperationsResponse,
  Announcement,
  AnnouncementCreate,
  AnnouncementUpdate,
  Settings,
  SettingsUpdate,
  SystemStatus,
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
  KBDeptGrant,
  KBDeptGrantsUpdate,
  EffectiveMember,
  MemoryItem,
} from '@/types/api'
import { TokenExpiredError, request, requestVoid, requestRaw } from './http'
import { report } from '../lib/monitor'
import { cachedDict, invalidateDict, invalidateDictPrefix } from './cache'

export async function getKnowledgeBases(
  page = 1,
  size = 20,
  q?: string,
  force = false,
): Promise<KnowledgeBasesResponse> {
  if (force) invalidateDictPrefix('kb:')
  const qs = new URLSearchParams({ page: String(page), size: String(size) })
  if (q) qs.set('q', q)
  const key = `kb:${page}:${size}:${q ?? ''}`
  return cachedDict(key, () => request<KnowledgeBasesResponse>(`/api/knowledge-bases?${qs.toString()}`))
}

/** 新建知识库（菜单级库：合规管理 / 广告运营 …）。 */
export async function createKnowledgeBase(payload: {
  name: string
  icon?: string | null
  description?: string | null
  category?: string | null
}): Promise<{ id: string; name: string; icon: string }> {
  invalidateDictPrefix('kb:')
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

/** 列出某知识库的部门授权记录。 */
export async function getKbDeptGrants(kbId: string): Promise<KBDeptGrant[]> {
  const data = await request<{ grants: KBDeptGrant[] }>(`/api/knowledge-bases/${kbId}/dept-grants`)
  return data.grants
}

/** 覆盖式设置某知识库的部门授权。 */
export async function setKbDeptGrants(kbId: string, payload: KBDeptGrantsUpdate): Promise<KBDeptGrant[]> {
  const data = await request<{ grants: KBDeptGrant[] }>(`/api/knowledge-bases/${kbId}/dept-grants`, {
    method: 'PUT',
    json: payload,
  })
  return data.grants
}

/** 预览某知识库的有效权限合并结果（个人 + 部门继承）。 */
export async function getKbEffectiveMembers(kbId: string): Promise<EffectiveMember[]> {
  const data = await request<{ members: EffectiveMember[] }>(`/api/knowledge-bases/${kbId}/effective-members`)
  return data.members
}

/** 列出当前用户全部长期记忆（按时间倒序）。 */
export async function getMemories(force = false): Promise<MemoryItem[]> {
  if (force) invalidateDict('mem')
  const data = await cachedDict('mem', () => request<{ memories: MemoryItem[] }>('/api/memories'))
  return data.memories
}

/** 删除一条记忆。 */
export async function deleteMemory(id: string): Promise<void> {
  invalidateDict('mem')
  await requestVoid(`/api/memories/${id}`, { method: 'DELETE' })
}

/** 清空当前用户全部记忆。 */
export async function clearMemories(): Promise<number> {
  invalidateDict('mem')
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
  opts?: { page?: number; size?: number; scope?: string; type?: string; status?: string; q?: string; mine?: boolean; departmentId?: string },
  force = false,
): Promise<DocumentList> {
  if (force) invalidateDictPrefix(`doc:${kbId}:`)
  const params = new URLSearchParams()
  if (opts?.page) params.set('page', String(opts.page))
  if (opts?.size) params.set('size', String(opts.size))
  if (opts?.scope) params.set('scope', opts.scope)
  if (opts?.type) params.set('type', opts.type)
  if (opts?.status) params.set('status', opts.status)
  if (opts?.q) params.set('q', opts.q)
  if (opts?.mine) params.set('mine', 'true')
  if (opts?.departmentId) params.set('department_id', opts.departmentId)
  const qs = params.toString()
  const key = `doc:${kbId}:${qs}`
  return cachedDict(key, () => request<DocumentList>(`/api/knowledge-bases/${kbId}/documents${qs ? `?${qs}` : ''}`))
}

/** 上传单篇文档（.md / .txt / .docx / .pdf）。
 *  两种提交方式（互斥，优先 fileUrl）：
 *   - fileUrl：前端已直传 OSS，只回传可访问地址，后端按 URL 回抓字节解析
 *   - contentB64：旧流程，前端把文件读成 base64 原始字节提交 */
export async function uploadDocument(
  kbId: string,
  filename: string,
  opts?: { contentB64?: string; fileUrl?: string; scope?: string; departmentId?: string },
): Promise<DocumentItem> {
  const body: Record<string, unknown> = { filename }
  if (opts?.fileUrl) body.fileUrl = opts.fileUrl
  else if (opts?.contentB64) body.contentB64 = opts.contentB64
  // scope 补全：上传时指定文档权限范围（private 仅本人可见），不传后端默认 public
  if (opts?.scope) body.scope = opts.scope
  // 部门文档：显式指定归属部门；scope=department 不传则后端默认取上传者部门
  if (opts?.departmentId) body.departmentId = opts.departmentId
  invalidateDictPrefix(`doc:${kbId}:`)
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
  invalidateDictPrefix(`doc:${kbId}:`)
  return request(`/api/knowledge-bases/${kbId}/documents/${docId}/approve`, { method: 'POST' })
}

/** 批量审核通过 */
export async function batchApproveDocuments(kbId: string, docIds: string[]): Promise<{ approved: number; skipped: number; failed: number }> {
  invalidateDictPrefix(`doc:${kbId}:`)
  return request(`/api/knowledge-bases/${kbId}/documents/batch-approve`, {
    method: 'POST',
    json: { doc_ids: docIds },
  })
}

/** 审核驳回：状态改为已拒绝，不摄入。 */
export async function rejectDocument(kbId: string, docId: string): Promise<DocumentItem> {
  invalidateDictPrefix(`doc:${kbId}:`)
  return request(`/api/knowledge-bases/${kbId}/documents/${docId}/reject`, { method: 'POST' })
}

/** 删除文档：级联清理 chunk / ES / 图谱 / 对象存储。 */
export async function deleteDocument(kbId: string, docId: string): Promise<void> {
  invalidateDictPrefix(`doc:${kbId}:`)
  await requestVoid(`/api/knowledge-bases/${kbId}/documents/${docId}`, { method: 'DELETE' })
}

/** AI 辅助审核文档。 */
export async function aiReviewDocument(
  kbId: string,
  docId: string,
): Promise<AIReview> {
  invalidateDictPrefix(`doc:${kbId}:`)
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
  force = false,
): Promise<RecordsResponse> {
  if (force) invalidateDictPrefix('rec:')
  const params = new URLSearchParams()
  if (opts?.page) params.set('page', String(opts.page))
  if (opts?.size) params.set('size', String(opts.size))
  if (opts?.filter) params.set('f', opts.filter)
  const qs = params.toString()
  const key = `rec:${qs}`
  return cachedDict(key, () => request<RecordsResponse>(`/api/records${qs ? `?${qs}` : ''}`))
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
  invalidateDictPrefix('kb:')
  return request(`/api/knowledge-bases/${id}`, { method: 'PUT', json: payload })
}

/** 删除单个知识库（级联清理其下文档 / 向量 / 图谱）。 */
export async function deleteKnowledgeBase(id: string): Promise<void> {
  invalidateDictPrefix('kb:')
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

/** 节点管理表格的分页列表 — 服务端过滤/分页/名称搜索，不受画布采样 limit 限制。 */
export async function getGraphNodes(query: GraphNodeListQuery = {}): Promise<GraphNodeListResult> {
  const params = new URLSearchParams()
  if (query.kbId) params.set('kb_id', query.kbId)
  if (query.nodeType) params.set('node_type', query.nodeType)
  if (query.q) params.set('q', query.q)
  params.set('page', String(query.page ?? 1))
  params.set('page_size', String(query.pageSize ?? 15))
  return request(`/api/graph/nodes?${params.toString()}`)
}

/** 关系检索表格的分页列表 — 服务端过滤/分页/搜索，不受画布采样 limit 限制。 */
export async function getGraphEdges(query: GraphEdgeListQuery = {}): Promise<GraphEdgeListResult> {
  const params = new URLSearchParams()
  if (query.kbId) params.set('kb_id', query.kbId)
  if (query.relation) params.set('relation', query.relation)
  if (query.q) params.set('q', query.q)
  params.set('page', String(query.page ?? 1))
  params.set('page_size', String(query.pageSize ?? 15))
  return request(`/api/graph/edges?${params.toString()}`)
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

/** 实体溯源：获取节点的源文档/chunk 信息。 */
export async function getGraphNodeSource(nodeId: string): Promise<GraphNodeSource> {
  return request(`/api/graph/nodes/${nodeId}/source`)
}

/** 创建实体节点。 */
export async function createGraphNode(body: { label: string; type?: string; kbId: string; chunkId?: string }): Promise<GraphNode> {
  return request('/api/graph/nodes', { method: 'POST', json: body })
}

/** 修改实体节点。 */
export async function updateGraphNode(nodeId: string, body: { label?: string; type?: string }): Promise<GraphNode> {
  return request(`/api/graph/nodes/${nodeId}`, { method: 'PUT', json: body })
}

/** 删除实体节点（级联删边）。 */
export async function deleteGraphNode(nodeId: string): Promise<void> {
  return requestVoid(`/api/graph/nodes/${nodeId}`, { method: 'DELETE' })
}

/** 创建关系边。 */
export async function createGraphEdge(body: { fromId: string; toId: string; relation: string }): Promise<{ id: string }> {
  return request('/api/graph/edges', { method: 'POST', json: body })
}

/** 删除关系边。 */
export async function deleteGraphEdge(edgeId: string): Promise<void> {
  return requestVoid(`/api/graph/edges/${edgeId}`, { method: 'DELETE' })
}

/** 合并实体。返回结构化摘要（删除了几个、重定向/删除几条边）。 */
export async function mergeGraphNodes(body: GraphMergeRequest): Promise<GraphMergeResult> {
  return request('/api/graph/merge', { method: 'POST', json: body })
}

/** 合并预览：只读计算合并影响（不写入），供确认前展示“会发生什么”。 */
export async function previewMergeGraphNodes(body: { kbId: string; sourceIds: string[]; targetLabel: string }): Promise<GraphMergePreview> {
  return request('/api/graph/merge/preview', { method: 'POST', json: body })
}

/** 知识缺口列表。 */
export async function getGraphGaps(kbId?: string | null, limit = 20): Promise<KGGapSignal[]> {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  if (kbId) params.set('kb_id', kbId)
  return request(`/api/graph/gaps?${params.toString()}`)
}

/** 标记缺口已处理。 */
export async function clearGraphGaps(kbId?: string | null, question?: string): Promise<void> {
  const params = new URLSearchParams()
  if (kbId) params.set('kb_id', kbId)
  if (question) params.set('question', question)
  const qs = params.toString()
  return request(`/api/graph/gaps${qs ? `?${qs}` : ''}`, { method: 'DELETE' })
}

/** 重建知识库图谱：对已审核文档重新 LLM 抽取。clean=true 先清图再全量重抽。 */
export async function rebuildGraph(
  kbId: string,
  clean = false,
): Promise<{ kbId: string; queuedDocs: number; clean: boolean }> {
  const params = new URLSearchParams()
  params.set('kb_id', kbId)
  params.set('clean', String(clean))
  return request(`/api/graph/rebuild?${params.toString()}`, { method: 'POST' })
}

/** 查询某 KB 图谱重建进度（前端轮询用）。status: running/done/failed/idle */
export async function getRebuildStatus(
  kbId: string,
): Promise<{ kbId: string; status: string; total: number; processed: number }> {
  return request(`/api/graph/rebuild/status?kb_id=${encodeURIComponent(kbId)}`)
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

/** 知识库文档分布（饼图数据源；知识库即文档的天然分类）。 */
export async function getKbDistribution(): Promise<KbDistribution[]> {
  return request('/api/analytics/kb-distribution')
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
  force = false,
): Promise<Paginated<Announcement>> {
  if (force) invalidateDictPrefix('ann:')
  const key = `ann:${page}:${size}`
  return cachedDict(key, () => request<Paginated<Announcement>>(`/api/announcements?page=${page}&size=${size}`))
}

/** 新建公告（仅 admin）。 */
export async function createAnnouncement(payload: AnnouncementCreate): Promise<Announcement> {
  invalidateDictPrefix('ann:')
  return request('/api/announcements', { method: 'POST', json: payload })
}

/** 更新公告（仅 admin）。 */
export async function updateAnnouncement(
  id: string,
  payload: AnnouncementUpdate,
): Promise<Announcement> {
  invalidateDictPrefix('ann:')
  return request(`/api/announcements/${id}`, { method: 'PUT', json: payload })
}

/** 删除公告（仅 admin）。 */
export async function deleteAnnouncement(id: string): Promise<void> {
  invalidateDictPrefix('ann:')
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

/* ---------- 字典 / 列表接口缓存（P4）----------
 * 实现抽到 ./cache（cachedDict / invalidateDict / invalidateDictPrefix / 5s TTL）。
 * 低频变化、被多处重复拉取的数据做 in-flight 去重 + 短 TTL 防重复调用；
 * 写接口成功后按 key（或前缀）主动失效，读取接口支持 force=true 绕过缓存。 */

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

/** 后端运行配置概览（只读、非机密）：模型配置页「当前状态」面板渲染用，
 *  避免前端写死值与后端实际配置脱节。带 60s 缓存。 */
export async function getSystemStatus(): Promise<SystemStatus> {
  return cachedDict('system-status', () => request<SystemStatus>('/api/settings/system'))
}

/** 文本转语音：返回 base64 音频 + contentType。前端拼 data URI 播放。P8 新增。 */
export async function ttsSpeak(text: string, voiceType?: number): Promise<TtsResult> {
  return request('/api/tts', { method: 'POST', json: { text, voiceType: voiceType ?? null } })
}

/** 部门树（嵌套）。P5 部门筛选使用；带 60s 缓存 + in-flight 去重。 */
export async function getDepartments(force = false): Promise<DepartmentNode[]> {
  if (force) invalidateDict('departments')
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

/** 同级部门拖拽排序（仅 admin）。parentId 为父级 id 或 null（顶级）；ids 为该层级完整有序列表。 */
export async function reorderDepartments(
  parentId: string | null,
  ids: string[],
): Promise<void> {
  await request('/api/departments/reorder', { method: 'POST', json: { parentId, ids } })
  invalidateDict('departments')
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
