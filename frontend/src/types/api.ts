export interface KnowledgeBase {
  id: string
  name: string
  icon: string
  badge: string | null
  badgeType: 'danger' | 'info' | null
  documentCount: number
  pendingCount: number
  description: string | null
  ownerDeptId?: string | null
  ownerDeptName?: string | null
}

/** 知识库成员（库级权限）。 */
export interface KBMember {
  userId: string
  username: string
  displayName: string | null
  level: 'view' | 'edit' | 'admin'
}

/** 全量设置知识库成员（覆盖式）。 */
export interface KBMembersUpdate {
  members: { userId: string; level: 'view' | 'edit' | 'admin' }[]
}

/** 部门授权记录。 */
export interface KBDeptGrant {
  id: string
  deptId: string
  deptName: string
  level: 'view' | 'edit' | 'admin'
}

/** 全量设置部门授权（覆盖式）。 */
export interface KBDeptGrantsUpdate {
  grants: { deptId: string; level: 'view' | 'edit' | 'admin' }[]
}

/** 有效权限预览条目（合并个人 + 部门继承）。 */
export interface EffectiveMember {
  userId: string
  username: string
  displayName: string | null
  level: 'view' | 'edit' | 'admin'
  source: string  // "direct" | "dept:部门名"
}

/** 长期记忆条目（个人记忆管理页）。 */
export interface MemoryItem {
  id: string
  content: string
  type: string | null
  createdAt: string | null
}

export interface KBCreate {
  name: string
  icon?: string | null
  description?: string | null
}

export interface KBUpdate {
  name?: string | null
  icon?: string | null
  description?: string | null
  ownerDeptId?: string | null
}

export interface KBReorder {
  orderedIds: string[]
}

export interface KBBatchDelete {
  ids: string[]
}

export interface HealthItem {
  kb: string
  docCount: number
  updatedAt: string
  reviewRate: number       // 审核率 = 已审核/总文档
  retrievableRate: number  // 可检索率 = 有向量文档/总文档
  freshnessHours: number | null  // 最近更新距现在小时，null=无文档
  healthScore: number      // 综合健康分
}

export interface TrendingItem {
  question: string
  count: number
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  pages: number
}

export interface DocumentItem {
  id: string
  title: string
  type: string      // 'MD' | 'TXT' | 'DOCX' | 'PDF'
  sizeKb: number
  status: string     // '已审核' | '待复核' | '已拒绝'
  updatedAt: string
  originalFilename?: string | null
  fileSize?: number | null
  uploaderName?: string | null   // P0：真实上传人显示名
  scope?: string                  // P0：权限范围 private|department|public
  parseStatus?: string            // P0：解析状态 pending|parsing|done|failed
}

export type DocumentList = Paginated<DocumentItem>

export interface DocumentDetail {
  id: string
  title: string
  type: string
  status: string
  contentMd: string
  originalFilename?: string | null
  fileSize?: number | null
  updatedAt: string
  reviewedAt?: string | null
  reviewedBy?: string | null
}

export interface AIReviewFinding {
  similarity: number
  docTitle: string
  docId: string
  snippet: string
  matchedChunk: string
}

export interface AIReview {
  verdict: 'approve' | 'reject' | 'manual_review'
  summary: string
  duplicates: string[]
  outdatedFindings: string[]
  qualityNotes: string[]
  suggestedKb: string | null
  similarityFindings: AIReviewFinding[]
}

export interface SourceItem {
  id: number
  chunkId: string
  kb: string
  kbId?: string          // KB UUID（查看文档详情用）
  title: string
  snippet: string
  confidence: number
  sourceType?: 'kb' | 'web' | 'graph'   // 来源类型：知识库 / 联网 / 知识图谱
  url?: string                // 联网来源的原始链接
  docId?: string               // 文档 UUID（查看文档详情用）
}

export interface SourceDetail {
  id: string
  title: string
  kb: string
  content: string
  chunkIndex: number
}

export interface ChatSession {
  id: string
  title: string
  updatedAt: string
  msgCount: number
  summary?: string | null
}

export interface SessionMessage {
  id?: string
  role: string
  content: string
  citations?: number[] | null
  sources?: SourceItem[] | null
  attachments?: ChatAttachment[] | null
  thinkingSteps?: ThinkingStep[] | null  // Agentic RAG 决策链（历史回显）
}

export interface SessionDetail {
  id: string
  title: string
  summary?: string | null
  messages: SessionMessage[]
}

/** Agent 决策步骤（Agentic RAG 的 thinking 事件） */
export interface ThinkingStep {
  step: number          // 第几步 (1-based)
  action: string        // 'direct_answer' | 'retrieve' | 'supplement_search'
  detail: string        // 中文描述，如"检索知识库：「选品策略」"
  rawReasoning?: string // LLM 原始推理文字（截断）
}

export interface ChatAttachment {
  kind: 'image' | 'audio' | 'video'
  mimeType: string
  dataB64?: string              // 纯 base64（无 `data:` 前缀）；旧流程发送与历史回显用
  url?: string                  // OSS 直传后的可访问地址；优先于 dataB64 发送给大模型
  name?: string | null
}

/** 兼容历史数据：早期后端曾在 DB 存 snake_case(mime_type/data_b64)。 */
export interface RawAttachment {
  kind?: 'image' | 'audio' | 'video'
  mimeType?: string
  mime_type?: string
  dataB64?: string
  data_b64?: string
  name?: string | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: number[]
  sources?: SourceItem[]
  attachments?: ChatAttachment[] | null  // 用户提问附带的图片等多模态
  thinkingSteps?: ThinkingStep[]  // Agentic RAG 决策链（仅 assistant）
  messageId?: string            // 服务端真实消息 id（来自 done 事件）
  feedback?: 'up' | 'down' | null  // 本地/服务端反馈状态
  stopped?: boolean               // 用户中途停止生成（保留已生成内容，标记不完整）
}

export interface FeedbackPayload {
  messageId: string
  rating: 'up' | 'down'
}

/* ===== 知识图谱（/api/graph） ===== */
export interface GraphNode {
  id: string
  label: string
  type: string | null
  kbId: string
  chunkId?: string | null
  createdAt?: string | null
}
export interface GraphEdge {
  id?: string
  source: string   // GraphNode.id
  target: string   // GraphNode.id
  relation: string
}
export interface GraphStats {
  nodeCount: number
  edgeCount: number
  kbCount: number
  typeCounts: Record<string, number>
}
export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: GraphStats
}

/** 热门实体（带度数，来自 /api/graph/hot-nodes）。 */
export interface GraphHotNode extends GraphNode {
  degree: number
}

/** 图谱筛选参数（透传后端 GET /api/graph）。 */
export interface GraphFilter {
  nodeType?: string
  from?: string   // ISO 日期，created_at >=
  to?: string     // ISO 日期，created_at <=
}

/** 节点分页列表查询参数（GET /api/graph/nodes）。 */
export interface GraphNodeListQuery {
  kbId?: string
  nodeType?: string
  q?: string        // 名称模糊搜索
  page?: number
  pageSize?: number
}

/** 节点分页列表返回 — 真·全集分页，不受画布采样 limit 限制。 */
export interface GraphNodeListResult {
  items: GraphNode[]
  total: number
}

/** 边分页列表查询参数（GET /api/graph/edges）。 */
export interface GraphEdgeListQuery {
  kbId?: string
  relation?: string
  q?: string        // 模糊搜索关系名/源实体/目标实体
  page?: number
  pageSize?: number
}

/** 边列表条目 — 直接携带源/目标 label（表格展示用）。 */
export interface GraphEdgeListItem {
  id: string
  sourceLabel: string
  targetLabel: string
  relation: string
  kbId: string
}

/** 边分页列表返回 — 真·全集分页，不受画布采样 limit 限制。 */
export interface GraphEdgeListResult {
  items: GraphEdgeListItem[]
  total: number
}

/** 实体溯源信息（GET /api/graph/nodes/{id}/source）。 */
export interface GraphNodeSource {
  docId: string | null
  docTitle: string | null
  kbId: string
  chunkContent: string | null
  chunkIndex: number | null
}

/** 实体合并请求。 */
export interface GraphMergeRequest {
  kbId: string
  sourceIds: string[]
  targetLabel: string
  targetType?: string | null
}

/** 合并影响摘要（preview 与 merge 共用同一套字段，保证“所见即所得”）。 */
export interface GraphMergeImpact {
  targetExists: boolean        // 目标名是否已是现有节点（将并入而非新建）
  nodesRemoved: number         // 将被删除的源实体数
  edgesRedirected: number      // 将被重定向的边数
  selfLoopsRemoved: number     // 合并后变成自环而被删除的边数
  duplicateEdgesRemoved: number // 重定向后重复而被去重的边数
  sourceTypes: string[]        // 源实体的类型集合
  typeConflict: boolean        // 源实体类型是否不一致
}

/** 合并预览响应。 */
export interface GraphMergePreview extends GraphMergeImpact {
  sources: GraphNode[]
  targetLabel: string
}

/** 合并执行结果。 */
export interface GraphMergeResult extends GraphMergeImpact {
  merged: number
  target: GraphNode
}

/** 知识缺口信号。 */
export interface KGGapSignal {
  question: string
  kbId: string
  count: number
  lastAt: string | null
}

export interface KnowledgeBasesResponse {
  knowledgeBases: KnowledgeBase[]
  health: HealthItem[]
  total: number
  page: number
  pageSize: number
  pages: number
}

export interface UserOut {
  id: string
  username: string
  displayName: string | null
  role: string         // 关联角色的 key（admin | editor | viewer | ...）
  roleId: string       // 关联角色 id（外键）
  isActive: boolean
  createdAt: string | null
  preferredModel?: string | null    // P8：偏好问答模型
  ttsEnabled?: boolean              // P8：是否启用语音播报
  email?: string | null
  departmentId?: string | null      // 部门 id（真相源）
  department?: string | null        // 部门显示名（后端按 id 解析）
  employeeId?: string | null
  permissions?: string[]            // 当前用户持有的权限 key 列表
}

export interface TokenOut {
  accessToken: string
  tokenType: string
  user: UserOut
}

export interface UserCreate {
  username: string
  password: string
  displayName?: string | null
  roleId: string       // 关联角色 id
  email?: string | null
  departmentId?: string | null
  employeeId?: string | null
}

export interface UserUpdate {
  displayName?: string | null
  roleId?: string
  isActive?: boolean
  password?: string
  email?: string | null
  departmentId?: string | null
  employeeId?: string | null
}

/** 角色定义（含权限集合）。 */
export interface RoleOut {
  id: string
  key: string
  name: string
  description: string | null
  isBuiltin: boolean
  sortOrder: number
  permissions: string[]
}

export interface RoleCreate {
  name: string
  key?: string
  description?: string | null
  permissions: string[]
}

export interface RoleUpdate {
  name?: string
  description?: string | null
}

export interface RolePermissions {
  permissions: string[]
}

/** 权限定义（后端 GET /api/permissions 返回）。 */
export interface PermissionDef {
  key: string
  label: string
  group: string
}

export type SSEEvent =
  | { event: 'thinking'; data: ThinkingStep }
  | { event: 'sources'; data: SourceItem[] }
  | { event: 'delta'; data: { content: string } }
  | { event: 'done'; data: { messageId: string; citations: number[]; sessionId: string } }
  | { event: 'follow_ups'; data: { questions: string[]; sessionTitle?: string | null } }
  | { event: 'ping'; data: unknown }
  | { event: 'error'; data: { message: string } }
  | { event: 'message'; data: unknown }

/* ===== Phase 1 业务统计（真实数据源，替代前端硬编码） ===== */
export interface DashboardMetrics {
  totalDocs: number
  todayNewDocs: number
  aiAnswers: number
  userSearches: number
  activeUsers: number
  deltas: {
    totalDocs: number
    todayNewDocs: number
    aiAnswers: number
    userSearches: number
    activeUsers: number
  }
}

export interface TrendPoint {
  date: string
  aiAnswers: number
  searches: number
}

export interface TrendResponse {
  range: 'today' | 'week' | 'month'
  labels: string[]
  points: TrendPoint[]
}

export interface KbDistribution {
  kbId: string
  name: string
  count: number
}

export interface DocTypeItem {
  type: string
  count: number
}

export interface RecentTrendPoint {
  date: string
  count: number
}

export interface UserStats {
  activeUsers: number
  totalUsers: number | null
  newUsers30: number | null
  byRole: { role: string; name: string; count: number }[]
  byStatus: { status: string; count: number }[]
  recentNew: RecentTrendPoint[]
  activeTrend: RecentTrendPoint[]
}

export interface DocStats {
  total: number
  byKb: KbDistribution[]
  byStatus: { status: string; count: number }[]
  byType: DocTypeItem[]
  recentTrend: RecentTrendPoint[]
}

export interface OperationLogItem {
  id: string
  userId: string | null
  displayName: string | null
  action: string
  actionLabel: string
  relatedDocId: string | null
  detail: string | null
  createdAt: string
}

export type OperationsResponse = Paginated<OperationLogItem>

/** 错误事件（错误管理页；backend=后端 4xx/5xx，frontend=前端上报）。 */
export interface ErrorEvent {
  id: string
  source: 'backend' | 'frontend' | string
  level: 'info' | 'warn' | 'error' | string
  method: string | null
  path: string | null
  statusCode: number | null
  rid: string | null
  etype: string | null
  message: string | null
  stack: string | null
  ip: string | null
  userAgent: string | null
  url: string | null
  requestBody: string | null
  createdAt: string
}

/** LLM 调用日志（调用日志页「模型调用」tab；stream_chat/chat/tool_call）。 */
export interface LLMCall {
  id: string
  model: string
  requestType: string
  caller: string | null
  status: 'success' | 'error' | string
  latencyMs: number | null
  tokensIn: number | null
  tokensOut: number | null
  error: string | null
  preview: string | null
  rid: string | null
  createdAt: string
}

export interface Announcement {
  id: string
  title: string
  content: string
  level: 'info' | 'warning' | 'success' | 'error'
  pinned: boolean
  createdAt: string
  read?: boolean
}

export interface AnnouncementCreate {
  title: string
  content: string
  level?: 'info' | 'warning' | 'success' | 'error'
  pinned?: boolean
}

export interface AnnouncementUpdate {
  title?: string
  content?: string
  level?: 'info' | 'warning' | 'success' | 'error'
  pinned?: boolean
}

/** 热门问答榜 / 知识缺口榜 单项。 */
export interface HotQueryItem {
  query: string
  count: number
}

/** 系统设置（个人偏好）。P8 新增；模型配置偏好(modelPrefs)服务端真值，前端不再用 localStorage。 */
export interface Settings {
  preferredModel: string | null        // 偏好问答模型；null=使用系统默认
  ttsEnabled: boolean                   // 是否启用语音播报
  modelPrefs: Record<string, unknown>  // 模型配置偏好（温度/TopP/最大长度/TopK/联网/来源数/provider/人设/思考/简洁）
}

export interface SettingsUpdate {
  preferredModel?: string | null
  ttsEnabled?: boolean
  modelPrefs?: Record<string, unknown>
}

/** 后端运行配置概览（只读、非机密）：模型配置页「当前状态」面板数据源，
 *  避免前端写死值与后端实际配置脱节。 */
export interface SystemStatus {
  defaultModel: string        // 「系统默认」实际对应的 LLM 模型
  embeddingModel: string
  embeddingDim: number
  reranker: string            // auto | cross-encoder | lexical-semantic | disabled
  graphEnabled: boolean
  memoryEnabled: boolean
  esEnabled: boolean          // ES 混合检索；false = pgvector 回退
  convSummaryEnabled: boolean
  ttsAvailable: boolean       // 腾讯 TTS 密钥是否已配置
  webProviders: string[]      // 可用联网搜索服务（含 ddg 免密钥兜底）
}

/** 语音合成结果：base64 音频 + MIME 类型，前端拼 data URI 播放。P8 新增。 */
export interface TtsResult {
  audio: string
  contentType: string
}

/** 部门树节点（递归 children）。P5 部门筛选使用。 */
export interface DepartmentNode {
  id: string
  name: string
  parentId: string | null
  description: string | null
  sortOrder: number
  createdAt: string
  children: DepartmentNode[]
}

/** 部门（扁平，用于列表页）。 */
export interface DepartmentOut {
  id: string
  name: string
  parentId: string | null
  description: string | null
  sortOrder: number
  createdAt: string
}

export interface DepartmentCreateIn {
  name: string
  parentId?: string | null
  description?: string | null
  sortOrder?: number
}

export interface DepartmentUpdateIn {
  name?: string
  parentId?: string | null
  description?: string | null
  sortOrder?: number
}

/** 文档处理任务（P5 上传进度轮询）。progress 0~100。 */
export interface DocumentTaskOut {
  id: string
  documentId: string | null
  kbId: string
  filename: string
  status: string
  progress: number
  currentStep: string
  errorMessage: string | null
  startedAt: string | null
  completedAt: string | null
  createdAt: string
  documentTitle: string | null
}

/** 全局文档搜索结果项（智能搜索页文档卡片）。 */
export interface SearchDocItem {
  id: string
  title: string
  type: string
  status: string
  updatedAt: string
  kbId: string
  kbName: string
  category: string | null
  scope: string
  uploaderName: string | null
  snippet: string
}

export type SearchDocsResponse = Paginated<SearchDocItem>

/** 检索记录单项（/api/records 服务端分页返回）。 */
export interface RecordItem {
  id: string
  sessionId: string
  sessionTitle: string
  question: string
  answer: string
  sources: SourceItem[] | null
  sourceCount: number
  kbCount: number
  webCount: number
  graphCount: number
  createdAt: string
}

export type RecordsResponse = Paginated<RecordItem>
