// 知识图谱共享数据层：四个图谱视图（全局图 / 节点 / 关系 / 统计）共用。
// 力导向布局与画布交互仅在「全局图谱」视图内，其余三视图只消费这里的数据。
import { ref, computed, watch, onMounted } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useToastStore } from '@/stores/toast'
import { getGraph, getGraphHotNodes, getGraphRecent, exportGraph } from '@/api'
import type { GraphData, GraphNode, GraphFilter, GraphHotNode } from '@/types/api'

export function useGraphData() {
  const knowledge = useKnowledgeStore()
  const toast = useToastStore()

  const graph = ref<GraphData | null>(null)
  const loading = ref(false)
  const errorMsg = ref('')
  const selectedKb = ref<string | null>(null)
  const searchTerm = ref('')
  const selectedId = ref<string | null>(null)
  const hoveredId = ref<string | null>(null)

  // 工具栏筛选（透传后端 GET /api/graph 真实过滤）
  const gFilterType = ref('')
  const gFilterBiz = ref('')
  const gFilterTime = ref('')

  // 节点类型选项：从已加载图谱的真实去重 type 派生（首次无类型过滤时采集）
  const allTypeOptions = ref<{ label: string; value: string }[]>([{ label: '全部', value: '' }])
  const bizCatOpts = computed<{ label: string; value: string }[]>(() => {
    const cats = Array.from(
      new Set(knowledge.bases.map((b) => b.category).filter((c): c is string => !!c)),
    )
    return [{ label: '全部', value: '' }, ...cats.map((c) => ({ label: c, value: c }))]
  })
  const nodeTypeOpts = computed(() => allTypeOptions.value)
  const timeRangeOpts = [
    { label: '全部时间', value: '' }, { label: '近 7 天', value: '7d' },
    { label: '近 30 天', value: '30d' }, { label: '近 90 天', value: '90d' },
  ]

  // 时间范围 → created_at 下限（ISO）
  function timeRangeToFromTo(v: string): { from?: string; to?: string } {
    if (!v) return {}
    const days = v === '7d' ? 7 : v === '30d' ? 30 : v === '90d' ? 90 : 0
    if (!days) return {}
    const d = new Date()
    d.setDate(d.getDate() - days)
    return { from: d.toISOString() }
  }

  // 真实筛选参数（随三个下拉变化）
  const graphFilter = computed<GraphFilter>(() => ({
    nodeType: gFilterType.value || undefined,
    bizCategory: gFilterBiz.value || undefined,
    ...timeRangeToFromTo(gFilterTime.value),
  }))

  // 右侧「热门实体 Top5 / 最近更新」来自服务端专门接口（替代前端近似）
  const hotNodes = ref<GraphHotNode[]>([])
  const recentNodes = ref<GraphNode[]>([])

  /* ---- KB 配色 / 名称 ---- */
  const PALETTE = ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#06B6D4', '#F97316', '#6366F1']
  const kbColor = computed<Record<string, string>>(() => {
    const m: Record<string, string> = {}
    knowledge.bases.forEach((b, i) => { m[b.id] = PALETTE[i % PALETTE.length] })
    return m
  })
  function nodeColor(kbId: string): string {
    return kbColor.value[kbId] || '#94A3B8'
  }
  function kbName(id: string): string {
    return knowledge.bases.find((b) => b.id === id)?.name || id
  }
  function nodeLabel(id: string): string {
    return graph.value?.nodes.find((n) => n.id === id)?.label || id
  }

  const degree = computed<Record<string, number>>(() => {
    const m: Record<string, number> = {}
    for (const e of graph.value?.edges || []) {
      m[e.source] = (m[e.source] || 0) + 1
      m[e.target] = (m[e.target] || 0) + 1
    }
    return m
  })

  const adjacency = computed<Record<string, Set<string>>>(() => {
    const m: Record<string, Set<string>> = {}
    for (const n of graph.value?.nodes || []) m[n.id] = new Set()
    for (const e of graph.value?.edges || []) {
      m[e.source]?.add(e.target)
      m[e.target]?.add(e.source)
    }
    return m
  })

  const presentKbs = computed(() => {
    const ids = new Set<string>()
    for (const n of graph.value?.nodes || []) ids.add(n.kbId)
    return knowledge.bases.filter((b) => ids.has(b.id))
  })

  /* ---- 统计面板派生数据 ---- */
  const stats = computed(() => graph.value?.stats)

  const docNodeCount = computed(() => {
    const tc = graph.value?.stats.typeCounts || {}
    return Object.entries(tc).filter(([k]) => k.includes('文档') || k.includes('doc')).reduce((s, [, v]) => s + v, 0) || graph.value?.nodes.length || 0
  })
  const conceptCount = computed(() => {
    const tc = graph.value?.stats.typeCounts || {}
    return Object.entries(tc).filter(([k]) => k.includes('知识') || k.includes('概念')).reduce((s, [, v]) => s + v, 0) || 0
  })
  const tagCount = computed(() => {
    const tc = graph.value?.stats.typeCounts || {}
    return Object.entries(tc).filter(([k]) => k.includes('标签')).reduce((s, [, v]) => s + v, 0) || 0
  })
  const bizCatCount = computed(() => {
    const tc = graph.value?.stats.typeCounts || {}
    return Object.entries(tc).filter(([k]) => k.includes('业务') || k.includes('分类')).reduce((s, [, v]) => s + v, 0) || 0
  })
  const typeBars = computed(() => {
    const tc = graph.value?.stats.typeCounts || {}
    const entries = Object.entries(tc).sort((a, b) => b[1] - a[1])
    const max = entries.length ? entries[0][1] : 1
    return entries.map(([label, count]) => ({ label, count, pct: Math.round((count / max) * 100) }))
  })

  const selectedNode = computed(() => graph.value?.nodes.find((n) => n.id === selectedId.value) || null)
  const selectedNeighbors = computed<string[]>(() => {
    const id = selectedId.value
    if (!id) return []
    const out: string[] = []
    for (const e of graph.value?.edges || []) {
      if (e.source === id) out.push(graph.value!.nodes.find((n) => n.id === e.target)?.label || e.target)
      else if (e.target === id) out.push(graph.value!.nodes.find((n) => n.id === e.source)?.label || e.source)
    }
    return out
  })

  /* ---- 节点表格 ---- */
  const nodeColumns = [
    { key: 'label', title: '实体', strong: true },
    { key: 'type', title: '类型' },
    { key: 'kb', title: '知识库' },
    { key: 'degree', title: '度数' },
  ]
  const nodePage = ref(1)
  const nodePageSize = ref(15)
  const pagedNodes = computed(() => {
    const nodes = graph.value?.nodes || []
    const start = (nodePage.value - 1) * nodePageSize.value
    return nodes.slice(start, start + nodePageSize.value)
  })

  /* ---- 关系检索 ---- */
  const relTerm = ref('')
  const filteredEdges = computed(() => {
    const t = relTerm.value.trim().toLowerCase()
    const edges = graph.value?.edges || []
    if (!t) return edges
    return edges.filter(
      (e) =>
        e.relation.toLowerCase().includes(t) ||
        nodeLabel(e.source).toLowerCase().includes(t) ||
        nodeLabel(e.target).toLowerCase().includes(t),
    )
  })

  /* ---- 画布平移/缩放状态（被全局视图的交互处理器变更）---- */
  const tx = ref(0)
  const ty = ref(0)
  const k = ref(1)
  function resetView() {
    tx.value = 0
    ty.value = 0
    k.value = 1
  }

  /* ---- 加载 ---- */
  async function fetchGraph() {
    loading.value = true
    errorMsg.value = ''
    try {
      const data = await getGraph(selectedKb.value, graphFilter.value)
      graph.value = data
      selectedId.value = null
      hoveredId.value = null
      resetView()
      // 无类型过滤时，用真实节点类型刷新下拉选项
      if (!gFilterType.value && data.nodes) {
        const types = Array.from(
          new Set(data.nodes.map((n) => n.type).filter((t): t is string => !!t)),
        )
        allTypeOptions.value = [
          { label: '全部', value: '' },
          ...types.map((t) => ({ label: t, value: t })),
        ]
      }
      await loadHotRecent()
    } catch (e: any) {
      errorMsg.value = e?.message || String(e)
      toast.error(`加载图谱失败：${errorMsg.value}`)
    } finally {
      loading.value = false
    }
  }

  async function loadHotRecent() {
    try {
      const [h, r] = await Promise.all([
        getGraphHotNodes(5, selectedKb.value),
        getGraphRecent(5, selectedKb.value),
      ])
      hotNodes.value = h
      recentNodes.value = r
    } catch {
      /* 非致命：侧栏列表缺失不影响主图 */
    }
  }

  function onExport() {
    exportGraph('json', selectedKb.value).catch((e: any) => {
      toast.error(`导出失败：${e?.message || e}`)
    })
  }

  function resetAll() {
    gFilterType.value = ''
    gFilterBiz.value = ''
    gFilterTime.value = ''
    searchTerm.value = ''
    selectedId.value = null
    hoveredId.value = null
    resetView()
    void fetchGraph()
  }

  onMounted(async () => {
    if (!knowledge.loaded) await knowledge.load().catch(() => {})
    await fetchGraph()
  })

  // 三个筛选下拉变化 → 重新拉图（后端真实过滤，节点集合随之变化）
  watch([gFilterType, gFilterBiz, gFilterTime], () => {
    void fetchGraph()
  })

  return {
    // 状态
    graph, loading, errorMsg, selectedKb, searchTerm, selectedId, hoveredId,
    gFilterType, gFilterBiz, gFilterTime, allTypeOptions, bizCatOpts, nodeTypeOpts, timeRangeOpts,
    graphFilter, hotNodes, recentNodes,
    // 派生
    kbColor, nodeColor, kbName, nodeLabel, degree, adjacency, presentKbs,
    stats, docNodeCount, conceptCount, tagCount, bizCatCount, typeBars,
    selectedNode, selectedNeighbors,
    nodeColumns, nodePage, nodePageSize, pagedNodes,
    relTerm, filteredEdges,
    // 画布
    tx, ty, k, resetView,
    // 动作
    fetchGraph, loadHotRecent, onExport, resetAll,
  }
}
