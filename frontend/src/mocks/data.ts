export interface KnowledgeBase {
  id: string
  name: string
  icon: string
  badge?: string
  badgeType?: 'danger' | 'info'
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: number[]
}

export interface SourceItem {
  id: number
  kb: string
  title: string
  snippet: string
  confidence: number
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

export const knowledgeBases: KnowledgeBase[] = [
  { id: 'compliance', name: '合规库', icon: 'compliance', badge: '5 份待复核', badgeType: 'danger' },
  { id: 'ads', name: '广告投放', icon: 'ads' },
  { id: 'logistics', name: '物流仓储', icon: 'logistics' },
  { id: 'selection', name: '选品策略', icon: 'selection' },
  { id: 'service', name: '客服话术', icon: 'service' },
]

export const workspaceEntries = ['我的收藏', '最近浏览', '团队共享']

export const messages: ChatMessage[] = [
  {
    id: 'u1',
    role: 'user',
    content: '美国站儿童玩具类目需要做 CPC 认证吗？上架前还要注意什么？',
  },
  {
    id: 'a1',
    role: 'assistant',
    content:
      '需要。美国站儿童玩具（12 岁及以下）强制要求 CPC 认证（Children’s Product Certificate），依据 CPSIA 与 ASTM F963 标准。上架前还需：1) 第三方实验室检测报告；2) 溯源标签（tracking label）；3) 小部件窒息警告（3 岁以下）。建议同步排查外观专利与商标侵权风险 [1][2]。',
    citations: [1, 2],
  },
]

export const sources: SourceItem[] = [
  {
    id: 1,
    kb: '合规库',
    title: 'CPC 认证办理指引',
    snippet:
      '儿童产品须经 CPSC 认可实验室检测，出具 CPC 证书，随货提供。检测覆盖铅含量、邻苯二甲酸盐及小部件测试……',
    confidence: 0.94,
  },
  {
    id: 2,
    kb: '合规库',
    title: '外观专利侵权排查清单',
    snippet:
      '上架前使用专利图片反向检索，重点排查美国 USPTO 外观专利，避免listing图片与已授权设计高度近似……',
    confidence: 0.88,
  },
]

export const health: HealthItem[] = [
  { kb: '合规库', docCount: 128, updatedAt: '2 小时前', coverage: 0.82 },
  { kb: '广告投放', docCount: 96, updatedAt: '昨天', coverage: 0.76 },
  { kb: '物流仓储', docCount: 74, updatedAt: '3 天前', coverage: 0.69 },
  { kb: '选品策略', docCount: 53, updatedAt: '1 周前', coverage: 0.61 },
  { kb: '客服话术', docCount: 41, updatedAt: '2 周前', coverage: 0.55 },
]

export const trending: TrendingItem[] = [
  { question: 'FBA 长期仓储费怎么算？', count: 38 },
  { question: '新品冷启动广告预算怎么分配？', count: 31 },
  { question: '类目审核需要哪些资质？', count: 27 },
  { question: '退货率过高如何申诉？', count: 19 },
]
