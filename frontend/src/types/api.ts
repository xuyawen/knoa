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

export interface SourceItem {
  id: number
  kb: string
  title: string
  snippet: string
  confidence: number
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
}

export interface KnowledgeBasesResponse {
  knowledgeBases: KnowledgeBase[]
  health: HealthItem[]
}

export type SSEEvent =
  | { event: 'thinking'; data: ThinkingStep }
  | { event: 'sources'; data: SourceItem[] }
  | { event: 'delta'; data: { content: string } }
  | { event: 'done'; data: { messageId: string; citations: number[]; sessionId: string } }
  | { event: 'error'; data: { message: string } }
