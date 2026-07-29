// 知识图谱共享数据层：四个图谱视图（全局图 / 节点 / 关系 / 统计）共用同一份模块级状态。
// 四个 tab 来回切换不会重复请求，筛选 / 分页 / 画布状态保留；「搜索」按钮或筛选变化强制刷新。
// 力导向布局与画布交互仅在「全局图谱」视图内，其余三视图只消费这里的数据。
import { ref, computed, watch, onMounted } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { getGraph, getGraphHotNodes, getGraphRecent, exportGraph, getGraphNodeSource, deleteGraphNode, updateGraphNode, createGraphNode, createGraphEdge, deleteGraphEdge, mergeGraphNodes, getGraphGaps, clearGraphGaps, rebuildGraph, getRebuildStatus } from '@/api'
import type { GraphData, GraphNode, GraphFilter, GraphHotNode, GraphNodeSource, KGGapSignal } from '@/types/api'

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

// 生效的知识库筛选：下拉选择优先，其次为外部预设的 selectedKb
const effectiveKb = computed<string | null>(() => gFilterBiz.value || selectedKb.value)

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

// 知识缺口信号
const gapSignals = ref<KGGapSignal[]>([])

// 子图聚焦模式
const focusNodeId = ref<string | null>(null)

// 是否已完成首次加载（模块级：仅第一个挂载的视图触发拉取）
let fetched = false

// 图谱重建状态（模块级共享：若放在 useGraphData() 内，视图重新挂载会产生
// 多个独立轮询链，重建完成时每个实例各弹一次成功提示）
const rebuilding = ref(false)
// 重建进度（供工具栏下方横幅展示）；null 表示无进行中/刚完成的重建
const rebuildProgress = ref<{ kbId: string; kbName: string; total: number; processed: number; status: string } | null>(null)
let rebuildTimer: ReturnType<typeof setTimeout> | null = null

/* ---- 导出工具：纯前端生成文件并触发下载（PNG / CSV 用） ---- */
export function dateStamp(): string {
  return new Date().toISOString().slice(0, 10)
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function csvEscape(v: string): string {
  return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v
}

function downloadText(text: string, filename: string): void {
  // BOM 前置：让 Excel 打开 CSV 时正确识别 UTF-8 中文
  downloadBlob(new Blob(['\ufeff' + text], { type: 'text/csv;charset=utf-8' }), filename)
}

export function useGraphData() {
  const knowledge = useKnowledgeStore()
  const toast = useToastStore()

  const bizCatOpts = computed<{ label: string; value: string }[]>(() => {
    return knowledge.bases.map((b) => ({ label: b.name, value: b.id }))
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

  /* ---- 按实体类型着色（单 KB 时也有丰富色彩） ---- */
  const TYPE_PALETTE = ['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#06B6D4', '#F97316', '#6366F1', '#14B8A6', '#E11D48', '#7C3AED', '#0EA5E9']
  const typeColorMap = computed<Record<string, string>>(() => {
    const m: Record<string, string> = {}
    const types = Object.keys(stats.value?.typeCounts || {})
    types.forEach((t, i) => { m[t] = TYPE_PALETTE[i % TYPE_PALETTE.length] })
    return m
  })
  function typeColor(type: string | undefined | null): string {
    if (!type) return '#94A3B8'
    return typeColorMap.value[type] || '#94A3B8'
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
      const data = await getGraph(effectiveKb.value, graphFilter.value)
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
        getGraphHotNodes(5, effectiveKb.value),
        getGraphRecent(5, effectiveKb.value),
      ])
      hotNodes.value = h
      recentNodes.value = r
    } catch {
      /* 非致命：侧栏列表缺失不影响主图 */
    }
  }

  /* ---- 导出：json/gexf 由后端生成；csv 纯前端从当前图谱数据生成 ---- */
  function exportRemote(fmt: 'json' | 'gexf') {
    return exportGraph(fmt, effectiveKb.value)
  }

  function exportCSV(which: 'nodes' | 'edges') {
    const g = graph.value
    if (!g) return
    let header: string
    let rows: string[][]
    let filename: string
    if (which === 'nodes') {
      header = '实体,类型,知识库,度数'
      rows = g.nodes.map((n) => [n.label, n.type || '', kbName(n.kbId), String(degree.value[n.id] || 0)])
      filename = `graph-nodes-${dateStamp()}.csv`
    } else {
      header = '起始实体,关系,目标实体'
      rows = g.edges.map((e) => [nodeLabel(e.source), e.relation, nodeLabel(e.target)])
      filename = `graph-edges-${dateStamp()}.csv`
    }
    const csv = [header, ...rows.map((r) => r.map(csvEscape).join(','))].join('\n')
    downloadText(csv, filename)
  }

  /* ---- 溯源 ---- */
  const sourceInfo = ref<GraphNodeSource | null>(null)
  const sourceLoading = ref(false)
  async function loadSource(nodeId: string) {
    sourceLoading.value = true
    sourceInfo.value = null
    try {
      sourceInfo.value = await getGraphNodeSource(nodeId)
    } catch (e: unknown) {
      toast.error(`加载溯源失败：${errMsg(e)}`)
    } finally {
      sourceLoading.value = false
    }
  }

  /* ---- 编辑操作 ---- */
  async function removeNode(nodeId: string) {
    try {
      await deleteGraphNode(nodeId)
      toast.success('实体已删除')
      selectedId.value = null
      await fetchGraph()
    } catch (e: unknown) {
      toast.error(`删除失败：${errMsg(e)}`)
    }
  }

  async function editNode(nodeId: string, label?: string, type?: string) {
    try {
      await updateGraphNode(nodeId, { label, type })
      toast.success('实体已更新')
      await fetchGraph()
    } catch (e: unknown) {
      toast.error(`更新失败：${errMsg(e)}`)
    }
  }

  async function addNode(label: string, type: string | undefined, kbId: string) {
    try {
      await createGraphNode({ label, type, kbId })
      toast.success('实体已创建')
      await fetchGraph()
    } catch (e: unknown) {
      toast.error(`创建失败：${errMsg(e)}`)
    }
  }

  async function addEdge(fromId: string, toId: string, relation: string) {
    try {
      await createGraphEdge({ fromId, toId, relation })
      toast.success('关系已创建')
      await fetchGraph()
    } catch (e: unknown) {
      toast.error(`创建关系失败：${errMsg(e)}`)
    }
  }

  async function removeEdge(edgeId: string) {
    try {
      await deleteGraphEdge(edgeId)
      toast.success('关系已删除')
      await fetchGraph()
    } catch (e: unknown) {
      toast.error(`删除关系失败：${errMsg(e)}`)
    }
  }

  async function mergeNodes(sourceIds: string[], targetLabel: string, targetType?: string) {
    const kbId = effectiveKb.value || graph.value?.nodes.find(n => sourceIds.includes(n.id))?.kbId
    if (!kbId) { toast.error('请先选择知识库'); return }
    try {
      await mergeGraphNodes({ kbId, sourceIds, targetLabel, targetType })
      toast.success('实体已合并')
      await fetchGraph()
    } catch (e: unknown) {
      toast.error(`合并失败：${errMsg(e)}`)
    }
  }

  /* ---- 图谱重建（存量已审核文档补抽 / 换模型后重抽） ---- */
  function stopRebuildPoll() {
    if (rebuildTimer) { clearTimeout(rebuildTimer); rebuildTimer = null }
  }

  async function rebuild(kbId: string, clean = false) {
    if (!kbId) { toast.error('请选择要重建的知识库'); return }
    try {
      const res = await rebuildGraph(kbId, clean)
      if (!res.queuedDocs) {
        toast.error('该知识库暂无已审核文档，无法重建图谱')
        return
      }
      rebuilding.value = true
      rebuildProgress.value = { kbId, kbName: kbName(kbId), total: res.queuedDocs, processed: 0, status: 'running' }
      toast.success(`已提交重建：${res.queuedDocs} 篇文档重新抽取中`)
      stopRebuildPoll()
      pollRebuild(kbId)
    } catch (e: unknown) {
      rebuilding.value = false
      rebuildProgress.value = null
      toast.error(`重建失败：${errMsg(e)}`)
    }
  }

  // 每 2s 轮询后端进度；running 继续，done/failed/idle 收尾
  function pollRebuild(kbId: string) {
    rebuildTimer = setTimeout(async () => {
      try {
        const st = await getRebuildStatus(kbId)
        const p = rebuildProgress.value
        if (p && p.kbId === kbId) {
          p.total = st.total || p.total
          p.processed = st.processed
          p.status = st.status
        }
        if (st.status === 'running') {
          pollRebuild(kbId)
        } else {
          await finishRebuild(st.status, kbId)
        }
      } catch {
        // 网络抖动：后端任务仍在跑，继续轮询
        pollRebuild(kbId)
      }
    }, 2000)
  }

  async function finishRebuild(status: string, kbId: string) {
    stopRebuildPoll()
    rebuilding.value = false
    // 仅当重建的就是当前正在查看的库时才刷新画布，避免切库后误刷其他库的图谱
    if (kbId === effectiveKb.value) {
      await fetchGraph().catch(() => {})
    }
    if (rebuildProgress.value) {
      rebuildProgress.value.status = status === 'done' ? 'done' : 'failed'
    }
    if (status === 'done') toast.success('图谱重建完成')
    else if (status === 'failed') toast.error('图谱重建异常，请重试')
    // 完成态横幅停留 5 秒后自动消失
    rebuildTimer = setTimeout(() => { rebuildProgress.value = null }, 5000)
  }

  // 进入页面时若该库仍在重建（如刷新后），恢复进度横幅 + 轮询
  async function resumeRebuildIfRunning(kbId: string | null) {
    if (!kbId || rebuilding.value) return
    try {
      const st = await getRebuildStatus(kbId)
      if (st.status === 'running') {
        rebuilding.value = true
        rebuildProgress.value = { kbId, kbName: kbName(kbId), total: st.total, processed: st.processed, status: 'running' }
        stopRebuildPoll()
        pollRebuild(kbId)
      }
    } catch { /* 非致命 */ }
  }

  /* ---- 知识缺口 ---- */
  async function loadGaps(allKbs = false) {
    try {
      gapSignals.value = await getGraphGaps(allKbs ? null : effectiveKb.value, 10)
    } catch { /* 非致命 */ }
  }
  async function dismissGap(kbId: string, question: string) {
    try {
      await clearGraphGaps(kbId, question)
      gapSignals.value = gapSignals.value.filter(g => !(g.kbId === kbId && g.question === question))
    } catch (e: unknown) {
      toast.error(`操作失败：${errMsg(e)}`)
    }
  }

  /* ---- 子图聚焦 ---- */
  function enterFocus(nodeId: string) {
    focusNodeId.value = nodeId
  }
  function exitFocus() {
    focusNodeId.value = null
  }
  // 聚焦模式下的可见节点（N 跳邻域）
  const focusedNodeIds = computed<Set<string> | null>(() => {
    if (!focusNodeId.value) return null
    const result = new Set<string>([focusNodeId.value])
    // 2 跳邻域
    for (let hop = 0; hop < 2; hop++) {
      for (const id of [...result]) {
        for (const nb of adjacency.value[id] || []) result.add(nb)
      }
    }
    return result
  })

  function resetAll() {
    const defaultKb = knowledge.bases[0]?.id || ''
    const filtersDirty = gFilterType.value !== '' || gFilterBiz.value !== defaultKb || gFilterTime.value !== ''
    gFilterType.value = ''
    gFilterBiz.value = defaultKb
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
    // 默认选中第一个知识库（数据量大，全量视图不可读）
    if (!gFilterBiz.value && knowledge.bases.length) {
      gFilterBiz.value = knowledge.bases[0].id
      // watch 会触发 fetchGraph，无需手动拉取
    } else if (!fetched && !loading.value) {
      await fetchGraph()
    }
  })

  // 三个筛选下拉变化 → 重新拉图（后端真实过滤，节点集合随之变化）
  watch([gFilterType, gFilterBiz, gFilterTime], () => {
    void fetchGraph()
  })

  return {
    // 状态
    graph, loading, errorMsg, selectedKb, searchTerm, selectedId, hoveredId,
    gFilterType, gFilterBiz, gFilterTime, allTypeOptions, bizCatOpts, nodeTypeOpts, timeRangeOpts,
    graphFilter, hotNodes, recentNodes, gapSignals,
    focusNodeId, focusedNodeIds,
    sourceInfo, sourceLoading,
    // 派生
    kbColor, nodeColor, kbName, nodeById, nodeLabel, degree, adjacency, presentKbs,
        typeColor, typeColorMap,
    stats, typeBars, maxDegree, avgDegree,
    selectedNode, selectedNeighbors,
    nodeColumns, nodePage, nodePageSize, pagedNodes,
    relTerm, filteredEdges, relPage, relPageSize, pagedEdges,
    // 画布
    tx, ty, k, resetView,
    // 动作
    fetchGraph, loadHotRecent, exportRemote, exportCSV, resetAll,
    loadSource, removeNode, editNode, addNode, addEdge, removeEdge, mergeNodes,
    rebuild, rebuilding, rebuildProgress, resumeRebuildIfRunning,
    loadGaps, dismissGap, enterFocus, exitFocus,
  }
}
