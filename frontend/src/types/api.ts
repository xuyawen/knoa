export interface KnowledgeBase {
  id: string
  name: string
  icon: string
  badge: string | null
  badgeType: 'danger' | 'info' | null
  documentCount: number
  pendingCount: number
  description: string | null
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

export interface DocumentItem {
  id: string
  title: string
  type: string      // 'MD' | 'TXT' | 'DOCX' | 'PDF'
  sizeKb: number
  status: string     // '已审核' | '待复核' | '已拒绝'
  updatedAt: string
  originalFilename?: string | null
  fileSize?: number | null
}

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
  title: string
  snippet: string
  confidence: number
  sourceType?: 'kb' | 'web' | 'graph'   // 来源类型：知识库 / 联网 / 知识图谱
  url?: string                // 联网来源的原始链接
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
}

export interface SessionMessage {
  role: string
  content: string
  citations?: number[] | null
  sources?: SourceItem[] | null
  attachments?: ChatAttachment[] | null
}

export interface SessionDetail {
  id: string
  title: string
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
  dataB64?: string              // 纯 base64（无 `data:` 前缀）；发送与历史回显都用它
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
}

export interface FeedbackPayload {
  messageId: string
  rating: 'up' | 'down'
}

export interface KnowledgeBasesResponse {
  knowledgeBases: KnowledgeBase[]
  health: HealthItem[]
}

export interface UserOut {
  id: string
  username: string
  displayName: string | null
  role: string         // admin | editor | viewer
  isActive: boolean
  createdAt: string | null
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
  role?: string       // 默认 viewer
}

export interface UserUpdate {
  displayName?: string | null
  role?: string
  isActive?: boolean
  password?: string
}

export type SSEEvent =
  | { event: 'thinking'; data: ThinkingStep }
  | { event: 'sources'; data: SourceItem[] }
  | { event: 'delta'; data: { content: string } }
  | { event: 'done'; data: { messageId: string; citations: number[]; sessionId: string } }
  | { event: 'error'; data: { message: string } }
