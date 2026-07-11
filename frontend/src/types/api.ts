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

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: number[]
  sources?: SourceItem[]
}

export interface KnowledgeBasesResponse {
  knowledgeBases: KnowledgeBase[]
  health: HealthItem[]
}

export type SSEEvent =
  | { event: 'sources'; data: SourceItem[] }
  | { event: 'delta'; data: { content: string } }
  | { event: 'done'; data: { messageId: string; citations: number[]; sessionId: string } }
  | { event: 'error'; data: { message: string } }
