// 知识图谱共享数据层：四个图谱视图（全局图 / 节点 / 关系 / 统计）共用同一份模块级状态。
// 四个 tab 来回切换不会重复请求，筛选 / 分页 / 画布状态保留；「搜索」按钮或筛选变化强制刷新。
// 力导向布局与画布交互仅在「全局图谱」视图内，其余三视图只消费这里的数据。
import { ref, computed, watch, onMounted } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { getGraph, getGraphHotNodes, getGraphRecent, exportGraph } from '@/api'
import type { GraphData, GraphNode, GraphFilter, GraphHotNode } from '@/types/api'

/* ---- 模块级共享状态：四个视图拿到同一套 refs ---- */
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

// 右侧「热门实体 Top5 / 最近更新」来自服务端专门接口
const hotNodes = ref<GraphHotNode[]>([])
const recentNodes = ref<GraphNode[]>([])

// 节点表格 / 关系列表分页状态
const nodePage = ref(1)
const nodePageSize = ref(15)
const relTerm = ref('')
const relPage = ref(1)
const relPageSize = ref(15)

// 画布平移/缩放状态（被全局视图的交互处理器变更）
const tx = ref(0)
const ty = ref(0)
const k = ref(1)

// 是否已完成首次加载（模块级：仅第一个挂载的视图触发拉取）
let fetched = false

export function useGraphData() {
  const knowledge = useKnowledgeStore()
  const toast = useToastStore()

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

  /* ---- 节点索引：替代模板 / 边过滤里的 O(N) find ---- */
  const nodeById = computed<Record<string, GraphNode>>(() => {
    const m: Record<string, GraphNode> = {}
    for (const n of graph.value?.nodes || []) m[n.id] = n
    return m
  })
  function nodeLabel(id: string): string {
    return nodeById.value[id]?.label || id
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

  // 类型分布条（typeCounts 来自后端按过滤全集的 GROUP BY 聚合）
  const typeBars = computed(() => {
    const tc = graph.value?.stats.typeCounts || {}
    const entries = Object.entries(tc).sort((a, b) => b[1] - a[1])
    const max = entries.length ? entries[0][1] : 1
    return entries.map(([label, count]) => ({ label, count, pct: Math.round((count / max) * 100) }))
  })

  // 渲染采样图谱的密度指标
  const maxDegree = computed(() => {
    let m = 0
    for (const v of Object.values(degree.value)) if (v > m) m = v
    return m
  })
  const avgDegree = computed(() => {
    const n = graph.value?.nodes.length || 0
    const e = graph.value?.edges.length || 0
    return n ? Math.round(((2 * e) / n) * 10) / 10 : 0
  })

  const selectedNode = computed(() => (selectedId.value ? nodeById.value[selectedId.value] || null : null))
  const selectedNeighbors = computed<string[]>(() => {
    const id = selectedId.value
    if (!id) return []
    const out: string[] = []
    for (const e of graph.value?.edges || []) {
      if (e.source === id) out.push(nodeById.value[e.target]?.label || e.target)
      else if (e.target === id) out.push(nodeById.value[e.source]?.label || e.source)
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
  const pagedNodes = computed(() => {
    const nodes = graph.value?.nodes || []
    const start = (nodePage.value - 1) * nodePageSize.value
    return nodes.slice(start, start + nodePageSize.value)
  })

  /* ---- 关系检索 ---- */
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
  // 关系列表前端分页（同节点表格模式）：大图谱下避免全量渲染长列表卡顿
  const pagedEdges = computed(() => {
    const start = (relPage.value - 1) * relPageSize.value
    return filteredEdges.value.slice(start, start + relPageSize.value)
  })
  // 检索词变化时回到第一页，避免停在超出结果集的页码
  watch(relTerm, () => { relPage.value = 1 })

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
      nodePage.value = 1
      relPage.value = 1
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
      fetched = true
    } catch (e: unknown) {
      errorMsg.value = errMsg(e)
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
    exportGraph('json', selectedKb.value).catch((e: unknown) => {
      toast.error(`导出失败：${errMsg(e)}`)
    })
  }

  function resetAll() {
    const filtersDirty = gFilterType.value !== '' || gFilterBiz.value !== '' || gFilterTime.value !== ''
    gFilterType.value = ''
    gFilterBiz.value = ''
    gFilterTime.value = ''
    searchTerm.value = ''
    selectedId.value = null
    hoveredId.value = null
    resetView()
    // 筛选本来为空时 watch 不会触发，需手动拉取；否则交给 watch，避免双重请求
    if (!filtersDirty) void fetchGraph()
  }

  onMounted(async () => {
    if (!knowledge.loaded) await knowledge.load().catch(() => {})
    // 共享状态只在首次挂载拉取；tab 切换直接复用（「搜索」按钮 / 筛选可强制刷新）
    if (!fetched && !loading.value) await fetchGraph()
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
    kbColor, nodeColor, kbName, nodeById, nodeLabel, degree, adjacency, presentKbs,
    stats, typeBars, maxDegree, avgDegree,
    selectedNode, selectedNeighbors,
    nodeColumns, nodePage, nodePageSize, pagedNodes,
    relTerm, filteredEdges, relPage, relPageSize, pagedEdges,
    // 画布
    tx, ty, k, resetView,
    // 动作
    fetchGraph, loadHotRecent, onExport, resetAll,
  }
}
