export interface KnowledgeBase {
  id: string
  name: string
  icon: string
  badge: string | null
  badgeType: 'danger' | 'info' | null
}

export interface HealthItem {
  kb: string
  docCount: number
  updatedAt: string
  coverage: number
}

export interface TrendingItem {
  question: string
  count: number
}

export interface DocumentItem {
  id: string
  title: string
  type: string      // 'MD' | 'TXT'
  sizeKb: number
  status: string     // '已审核' | '待复核'
  updatedAt: string
}

export interface SourceItem {
  id: number
  chunkId: string
  kb: string
  title: string
  snippet: string
  confidence: number
  sourceType?: 'kb' | 'web'   // 来源类型：知识库 / 联网
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

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: number[]
  sources?: SourceItem[]
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
