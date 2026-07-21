<script setup lang="ts">
// 知识图谱 — 接真实 /api/graph（kg_node / kg_edge）。
// 用客户端力导向布局渲染实体关系图，支持拖拽 / 缩放 / 平移 / 悬浮高亮 / 点击查看。
// 右侧统计面板全部取自接口真实数据（节点/边/库数、类型分布、按度数 Top、最近新增）。
// section 由路由决定（global/nodes/relations/stats）。
import { ref, computed, onMounted, nextTick } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import { useToastStore } from '@/stores/toast'
import { useKnowledgeStore } from '@/stores/knowledge'
import { getGraph } from '@/api'
import type { GraphData, GraphNode, GraphEdge } from '@/types/api'

const toast = useToastStore()
const knowledge = useKnowledgeStore()

const props = defineProps<{ section?: string }>()
const section = computed(() => props.section ?? 'global')

// 关系检索（relations 分区）
const relTerm = ref('')
function nodeLabel(id: string): string {
  return graph.value?.nodes.find((n) => n.id === id)?.label || id
}
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

const graph = ref<GraphData | null>(null)
const loading = ref(false)
const errorMsg = ref('')
const selectedKb = ref<string | null>(null)
const searchTerm = ref('')
const selectedId = ref<string | null>(null)
const hoveredId = ref<string | null>(null)

/* ---- 力导向布局 ---- */
interface LNode { id: string; x: number; y: number; deg: number; r: number }
const W = 900
const H = 560
const lNodes = ref<LNode[]>([])
const tx = ref(0)
const ty = ref(0)
const k = ref(1)
const svgRef = ref<SVGSVGElement | null>(null)

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

function computeLayout(nodes: GraphNode[], edges: GraphEdge[]): LNode[] {
  const n = nodes.length
  const arr: LNode[] = nodes.map((nd, i) => {
    const ang = (i / Math.max(1, n)) * Math.PI * 2
    const rad = Math.min(W, H) * 0.4
    return {
      id: nd.id,
      x: W / 2 + Math.cos(ang) * rad,
      y: H / 2 + Math.sin(ang) * rad,
      deg: degree.value[nd.id] || 0,
      r: 6 + Math.min(13, Math.sqrt(degree.value[nd.id] || 0) * 3),
    }
  })
  const idx: Record<string, number> = {}
  arr.forEach((a, i) => { idx[a.id] = i })

  const REP = 6000
  const SPRING = 0.04
  const REST = 72
  const CENTER = 0.008
  for (let it = 0; it < 240; it++) {
    // 斥力（库仑）
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = arr[i].x - arr[j].x
        let dy = arr[i].y - arr[j].y
        const d2 = dx * dx + dy * dy + 0.01
        const f = REP / d2
        const d = Math.sqrt(d2)
        const fx = (dx / d) * f
        const fy = (dy / d) * f
        arr[i].x += fx; arr[i].y += fy
        arr[j].x -= fx; arr[j].y -= fy
      }
    }
    // 引力（弹簧，沿边）
    for (const e of edges) {
      const a = idx[e.source]
      const b = idx[e.target]
      if (a == null || b == null) continue
      let dx = arr[b].x - arr[a].x
      let dy = arr[b].y - arr[a].y
      const d = Math.sqrt(dx * dx + dy * dy) + 0.01
      const f = SPRING * (d - REST)
      const fx = (dx / d) * f
      const fy = (dy / d) * f
      arr[a].x += fx; arr[a].y += fy
      arr[b].x -= fx; arr[b].y -= fy
    }
    // 向心
    for (let i = 0; i < n; i++) {
      arr[i].x += (W / 2 - arr[i].x) * CENTER
      arr[i].y += (H / 2 - arr[i].y) * CENTER
      if (arr[i].x < 20) arr[i].x = 20
      if (arr[i].x > W - 20) arr[i].x = W - 20
      if (arr[i].y < 20) arr[i].y = 20
      if (arr[i].y > H - 20) arr[i].y = H - 20
    }
  }
  return arr
}

const posMap = computed<Record<string, { x: number; y: number }>>(() => {
  const m: Record<string, { x: number; y: number }> = {}
  for (const n of lNodes.value) m[n.id] = { x: n.x, y: n.y }
  return m
})

/* ---- 高亮（悬浮 / 选中 / 搜索） ---- */
const focusId = computed(() => hoveredId.value ?? selectedId.value)
const activeIds = computed<Set<string> | null>(() => {
  const set = new Set<string>()
  const term = searchTerm.value.trim().toLowerCase()
  if (term) {
    for (const n of graph.value?.nodes || []) {
      if (n.label.toLowerCase().includes(term)) set.add(n.id)
    }
  } else if (focusId.value) {
    set.add(focusId.value)
  } else {
    return null // null = 全部高亮
  }
  if (set.size) {
    const extra: string[] = []
    for (const id of set) for (const nb of (adjacency.value[id] || [])) extra.push(nb)
    extra.forEach((x) => set.add(x))
  }
  return set
})
function nodeDim(id: string): boolean {
  const a = activeIds.value
  return a ? !a.has(id) : false
}
function edgeDim(e: GraphEdge): boolean {
  const a = activeIds.value
  if (!a) return false
  return !(a.has(e.source) && a.has(e.target))
}

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
const presentKbs = computed(() => {
  const ids = new Set<string>()
  for (const n of graph.value?.nodes || []) ids.add(n.kbId)
  return knowledge.bases.filter((b) => ids.has(b.id))
})

/* ---- 统计面板派生数据 ---- */
const stats = computed(() => graph.value?.stats)
const typeBars = computed(() => {
  const tc = graph.value?.stats.typeCounts || {}
  const entries = Object.entries(tc).sort((a, b) => b[1] - a[1])
  const max = entries.length ? entries[0][1] : 1
  return entries.map(([label, count]) => ({ label, count, pct: Math.round((count / max) * 100) }))
})
const topNodes = computed(() =>
  [...(graph.value?.nodes || [])]
    .map((n) => ({ node: n, deg: degree.value[n.id] || 0 }))
    .sort((a, b) => b.deg - a.deg)
    .slice(0, 6),
)
const recentNodes = computed(() =>
  [...(graph.value?.nodes || [])]
    .filter((n) => n.createdAt)
    .sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''))
    .slice(0, 6),
)
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

/* ---- 交互：平移 / 拖拽 / 缩放 ---- */
let panning = false
let dragging: string | null = null
let lastRoot: { x: number; y: number } | null = null

function toRoot(clientX: number, clientY: number) {
  const svg = svgRef.value
  if (!svg) return { x: 0, y: 0 }
  const ctm = svg.getScreenCTM()
  if (!ctm) return { x: 0, y: 0 }
  const inv = ctm.inverse()
  return { x: clientX * inv.a + clientY * inv.b + inv.e, y: clientX * inv.c + clientY * inv.d + inv.f }
}
function toLocal(clientX: number, clientY: number) {
  const r = toRoot(clientX, clientY)
  return { x: (r.x - tx.value) / k.value, y: (r.y - ty.value) / k.value }
}
function onCanvasDown(e: PointerEvent) {
  if (dragging) return
  panning = true
  lastRoot = toRoot(e.clientX, e.clientY)
  ;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
}
function onNodeDown(e: PointerEvent, id: string) {
  e.stopPropagation()
  dragging = id
  lastRoot = null
  ;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
}
function onMove(e: PointerEvent) {
  if (dragging) {
    const l = toLocal(e.clientX, e.clientY)
    const nd = lNodes.value.find((x) => x.id === dragging)
    if (nd) { nd.x = l.x; nd.y = l.y }
  } else if (panning && lastRoot) {
    const r = toRoot(e.clientX, e.clientY)
    tx.value += r.x - lastRoot.x
    ty.value += r.y - lastRoot.y
    lastRoot = r
  }
}
function onUp() {
  panning = false
  dragging = null
}
function onWheel(e: WheelEvent) {
  e.preventDefault()
  const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
  k.value = Math.min(3, Math.max(0.3, k.value * factor))
}
function zoom(dir: number) {
  k.value = Math.min(3, Math.max(0.3, k.value * (dir > 0 ? 1.2 : 1 / 1.2)))
}
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
    const data = await getGraph(selectedKb.value)
    graph.value = data
    lNodes.value = computeLayout(data.nodes, data.edges)
    selectedId.value = null
    hoveredId.value = null
    resetView()
    await nextTick()
  } catch (e: any) {
    errorMsg.value = e?.message || String(e)
    toast.error(`加载图谱失败：${errorMsg.value}`)
  } finally {
    loading.value = false
  }
}

function resetAll() {
  searchTerm.value = ''
  selectedId.value = null
  hoveredId.value = null
  resetView()
}

onMounted(async () => {
  if (!knowledge.loaded) await knowledge.load().catch(() => {})
  await fetchGraph()
})
</script>

<template>
  <div class="graph-page">
    <h2 class="page-title">知识图谱</h2>

    <!-- ====== 全局图谱 ====== -->
    <template v-if="section === 'global'">
    <!-- ====== 工具栏 ====== -->
    <div class="graph-toolbar card">
      <div class="toolbar-left">
        <div class="g-search">
          <input v-model="searchTerm" type="text" placeholder="搜索实体名称高亮关联…" class="g-input" />
          <Icon name="search" :size="15" class="g-search-icon" />
        </div>
        <select v-model="selectedKb" class="g-select" @change="fetchGraph">
          <option :value="null">全部分类</option>
          <option v-for="b in knowledge.bases" :key="b.id" :value="b.id">{{ b.name }}</option>
        </select>
        <button class="btn btn-ghost btn-sm g-reset" @click="resetAll">重置</button>
      </div>
      <div class="toolbar-right">
        <button class="btn btn-primary btn-sm" :disabled="loading" @click="fetchGraph">
          <Icon name="refresh" :size="13" /> {{ loading ? '加载中…' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- ====== 主区：图布 + 右侧面板 ====== -->
    <div class="graph-body">
      <!-- 左：图布 -->
      <div class="canvas-area card">
        <!-- 加载 / 空态 / 图布 -->
        <div v-if="loading" class="canvas-state">
          <span class="dot" /><span class="dot" /><span class="dot" />
          <p>正在构建知识图谱…</p>
        </div>

        <div v-else-if="graph && graph.nodes.length === 0" class="canvas-state">
          <div class="empty-avatar"><Icon name="graph" :size="26" /></div>
          <p class="empty-title">暂无图谱数据</p>
          <p class="empty-sub">上传并审核文档后，系统会自动抽取实体与关系构建知识图谱。</p>
        </div>

        <svg
          v-else
          ref="svgRef"
          viewBox="0 0 900 560"
          class="force-graph"
          preserveAspectRatio="xMidYMid meet"
          @pointerdown="onCanvasDown"
          @pointermove="onMove"
          @pointerup="onUp"
          @pointerleave="onUp"
          @wheel.prevent="onWheel"
        >
          <defs>
            <marker id="arrow" markerWidth="9" markerHeight="9" refX="7.5" refY="3" orient="auto-start-reverse" markerUnits="strokeWidth">
              <path d="M0,0 L0,6 L8,3 z" fill="#94A3B8" />
            </marker>
          </defs>

          <g :transform="`translate(${tx},${ty}) scale(${k})`">
            <!-- 边 -->
            <g class="edges" fill="none">
              <template v-for="(e, i) in (graph?.edges || [])" :key="'e' + i">
                <g v-if="posMap[e.source] && posMap[e.target]" :class="{ dim: edgeDim(e) }">
                  <line
                    :x1="posMap[e.source].x" :y1="posMap[e.source].y"
                    :x2="posMap[e.target].x" :y2="posMap[e.target].y"
                    :stroke="focusId ? '#94A3B8' : '#CBD5E1'"
                    stroke-width="1.4"
                    marker-end="url(#arrow)"
                  />
                  <!-- 关系标签：仅在聚焦（悬浮/选中/搜索命中）时显示，避免拥挤 -->
                  <text
                    v-if="!edgeDim(e)"
                    :x="(posMap[e.source].x + posMap[e.target].x) / 2"
                    :y="(posMap[e.source].y + posMap[e.target].y) / 2 - 3"
                    class="edge-label"
                    text-anchor="middle"
                  >{{ e.relation }}</text>
                </g>
              </template>
            </g>

            <!-- 节点 -->
            <g class="nodes">
              <g
                v-for="n in lNodes"
                :key="n.id"
                :transform="`translate(${posMap[n.id].x},${posMap[n.id].y})`"
                :class="{ dim: nodeDim(n.id) }"
                class="gnode"
                @pointerenter="hoveredId = n.id"
                @pointerleave="hoveredId = null"
                @pointerdown="onNodeDown($event, n.id)"
                @click="selectedId = n.id"
              >
                <circle
                  :r="n.r"
                  :fill="nodeColor((graph?.nodes.find(x=>x.id===n.id)?.kbId) || '')"
                  :stroke="selectedId === n.id ? '#0F172A' : '#fff'"
                  :stroke-width="selectedId === n.id ? 2.5 : 1.5"
                />
                <text class="node-label" :y="n.r + 12" text-anchor="middle">{{ graph?.nodes.find(x=>x.id===n.id)?.label }}</text>
              </g>
            </g>
          </g>
        </svg>

        <!-- 底部控制 + 图例 -->
        <div v-if="graph && graph.nodes.length" class="canvas-footer">
          <div class="zoom-controls">
            <button class="zc-btn" title="缩小" @click="zoom(-1)"><Icon name="minus" :size="14" /></button>
            <span class="zoom-level">{{ Math.round(k * 100) }}%</span>
            <button class="zc-btn" title="放大" @click="zoom(1)"><Icon name="plus" :size="14" /></button>
            <button class="zc-btn" title="复位" @click="resetView"><Icon name="expand" :size="14" /></button>
          </div>
          <div class="legend">
            <span class="leg-item" v-for="b in presentKbs" :key="b.id">
              <i class="leg-dot" :style="{ background: kbColor[b.id] }"></i> {{ b.name }}
            </span>
            <span class="leg-divider"></span>
            <span class="leg-line"><i class="leg-arrow"></i> 关系</span>
          </div>
        </div>
        <p v-if="graph && graph.nodes.length" class="canvas-hint">拖拽节点可移动 · 滚轮缩放 · 拖拽空白处平移 · 点击查看详情</p>
      </div>

      <!-- 右：数据面板 -->
      <aside class="stats-panel card">
        <div class="panel-head">
          <span class="panel-title">图谱数据统计</span>
          <Icon name="graph" :size="14" class="info-hint" />
        </div>

        <!-- 统计数字 -->
        <div class="stat-grid">
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:#3B82F614"><Icon name="graph" :size="18" style="color:#3B82F6" /></div>
            <div class="sc-info"><div class="sc-label">实体节点</div><div class="sc-value" style="color:#3B82F6">{{ stats?.nodeCount ?? 0 }}</div></div>
          </div>
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:#10B98114"><Icon name="link" :size="18" style="color:#10B981" /></div>
            <div class="sc-info"><div class="sc-label">关系边</div><div class="sc-value" style="color:#10B981">{{ stats?.edgeCount ?? 0 }}</div></div>
          </div>
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:#8B5CF614"><Icon name="folder" :size="18" style="color:#8B5CF6" /></div>
            <div class="sc-info"><div class="sc-label">覆盖知识库</div><div class="sc-value" style="color:#8B5CF6">{{ stats?.kbCount ?? 0 }}</div></div>
          </div>
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:#F59E0B14"><Icon name="tag" :size="18" style="color:#F59E0B" /></div>
            <div class="sc-info"><div class="sc-label">实体类型</div><div class="sc-value" style="color:#F59E0B">{{ Object.keys(stats?.typeCounts || {}).length }}</div></div>
          </div>
        </div>

        <!-- 选中节点详情 -->
        <div v-if="selectedNode" class="section-block detail-box">
          <div class="section-title">实体详情</div>
          <div class="detail-name">{{ selectedNode.label }}</div>
          <div class="detail-meta">
            <span class="detail-tag" :style="{ background: nodeColor(selectedNode.kbId) + '22', color: nodeColor(selectedNode.kbId) }">{{ kbName(selectedNode.kbId) }}</span>
            <span v-if="selectedNode.type" class="detail-tag">{{ selectedNode.type }}</span>
          </div>
          <div class="detail-degree">关联度数：<strong>{{ degree[selectedNode.id] || 0 }}</strong></div>
          <div v-if="selectedNeighbors.length" class="detail-neighbors">
            <span class="dn-label">关联实体：</span>
            <span v-for="(nb, i) in selectedNeighbors" :key="i" class="dn-chip">{{ nb }}</span>
          </div>
        </div>

        <!-- 类型分布 -->
        <div class="section-block">
          <div class="section-title">实体类型分布</div>
          <div class="type-bars">
            <div v-for="(t, i) in typeBars" :key="i" class="type-bar">
              <span class="tb-label">{{ t.label }}</span>
              <span class="tb-track"><i class="tb-fill" :style="{ width: t.pct + '%' }"></i></span>
              <span class="tb-count">{{ t.count }}</span>
            </div>
          </div>
        </div>

        <!-- 高关联节点 -->
        <div class="section-block">
          <div class="section-title">高关联实体 Top 6</div>
          <div class="hot-list">
            <div v-for="(item, i) in topNodes" :key="item.node.id" class="hot-item" @click="selectedId = item.node.id" @mouseenter="hoveredId = item.node.id" @mouseleave="hoveredId = null">
              <span class="hot-rank" :class="{ top3: i < 3 }">{{ i + 1 }}</span>
              <span class="hot-dot" :style="{ background: nodeColor(item.node.kbId) }"></span>
              <span class="hot-name">{{ item.node.label }}</span>
              <span class="hot-count">度数 <strong>{{ item.deg }}</strong></span>
            </div>
          </div>
        </div>

        <!-- 最近新增 -->
        <div class="section-block">
          <div class="section-header">
            <span class="section-title">最近新增的实体</span>
          </div>
          <div class="recent-list">
            <div v-for="n in recentNodes" :key="n.id" class="recent-item" @click="selectedId = n.id" @mouseenter="hoveredId = n.id" @mouseleave="hoveredId = null">
              <span class="recent-icon" :style="{ background: nodeColor(n.kbId) + '18', color: nodeColor(n.kbId) }">
                <Icon name="graph" :size="13" />
              </span>
              <span class="recent-name">{{ n.label }}</span>
              <span class="recent-time">{{ (n.createdAt || '').slice(5, 10) }}</span>
            </div>
          </div>
        </div>
      </aside>
    </div>
    </template>

    <!-- ====== 节点管理 ====== -->
    <template v-else-if="section === 'nodes'">
      <div class="card node-card">
        <div class="panel-head">
          <span class="panel-title">实体节点（{{ graph?.nodes.length || 0 }}）</span>
          <Icon name="node" :size="14" class="info-hint" />
        </div>
        <div class="node-scroll">
          <table class="node-table">
            <thead>
              <tr><th>实体</th><th>类型</th><th>知识库</th><th>度数</th></tr>
            </thead>
            <tbody>
              <tr v-for="n in graph?.nodes" :key="n.id" @click="selectedId = n.id">
                <td class="col-name">{{ n.label }}</td>
                <td>{{ n.type || '—' }}</td>
                <td>{{ kbName(n.kbId) }}</td>
                <td>{{ degree[n.id] || 0 }}</td>
              </tr>
              <tr v-if="!graph || !graph.nodes.length">
                <td colspan="4" class="empty-hint">暂无实体节点</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ====== 关系检索 ====== -->
    <template v-else-if="section === 'relations'">
      <div class="card rel-card">
        <div class="panel-head">
          <span class="panel-title">关系检索</span>
          <Icon name="link" :size="14" class="info-hint" />
        </div>
        <div class="g-search" style="margin-bottom: 14px">
          <input v-model="relTerm" type="text" placeholder="搜索关系名称 / 实体…" class="g-input" />
          <Icon name="search" :size="15" class="g-search-icon" />
        </div>
        <div class="rel-list">
          <div v-for="(e, i) in filteredEdges" :key="i" class="rel-item">
            <span class="rel-src">{{ nodeLabel(e.source) }}</span>
            <span class="rel-arrow">{{ e.relation }}</span>
            <span class="rel-tgt">{{ nodeLabel(e.target) }}</span>
          </div>
          <div v-if="!filteredEdges.length" class="empty-hint">暂无匹配的关系</div>
        </div>
      </div>
    </template>

    <!-- ====== 图谱统计 ====== -->
    <template v-else>
      <div class="stats-page">
        <div class="stat-grid wide">
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:#3B82F614"><Icon name="graph" :size="18" style="color:#3B82F6" /></div>
            <div class="sc-info"><div class="sc-label">实体节点</div><div class="sc-value" style="color:#3B82F6">{{ stats?.nodeCount ?? 0 }}</div></div>
          </div>
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:#10B98114"><Icon name="link" :size="18" style="color:#10B981" /></div>
            <div class="sc-info"><div class="sc-label">关系边</div><div class="sc-value" style="color:#10B981">{{ stats?.edgeCount ?? 0 }}</div></div>
          </div>
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:#8B5CF614"><Icon name="folder" :size="18" style="color:#8B5CF6" /></div>
            <div class="sc-info"><div class="sc-label">覆盖知识库</div><div class="sc-value" style="color:#8B5CF6">{{ stats?.kbCount ?? 0 }}</div></div>
          </div>
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:#F59E0B14"><Icon name="tag" :size="18" style="color:#F59E0B" /></div>
            <div class="sc-info"><div class="sc-label">实体类型</div><div class="sc-value" style="color:#F59E0B">{{ Object.keys(stats?.typeCounts || {}).length }}</div></div>
          </div>
        </div>

        <div class="card stat-block">
          <div class="section-title">实体类型分布</div>
          <div class="type-bars">
            <div v-for="(t, i) in typeBars" :key="i" class="type-bar">
              <span class="tb-label">{{ t.label }}</span>
              <span class="tb-track"><i class="tb-fill" :style="{ width: t.pct + '%' }"></i></span>
              <span class="tb-count">{{ t.count }}</span>
            </div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card stat-block">
            <div class="section-title">高关联实体 Top 6</div>
            <div class="hot-list">
              <div v-for="(item, i) in topNodes" :key="item.node.id" class="hot-item" @click="selectedId = item.node.id">
                <span class="hot-rank" :class="{ top3: i < 3 }">{{ i + 1 }}</span>
                <span class="hot-dot" :style="{ background: nodeColor(item.node.kbId) }"></span>
                <span class="hot-name">{{ item.node.label }}</span>
                <span class="hot-count">度数 <strong>{{ item.deg }}</strong></span>
              </div>
            </div>
          </div>
          <div class="card stat-block">
            <div class="section-title">最近新增的实体</div>
            <div class="recent-list">
              <div v-for="n in recentNodes" :key="n.id" class="recent-item" @click="selectedId = n.id">
                <span class="recent-icon" :style="{ background: nodeColor(n.kbId) + '18', color: nodeColor(n.kbId) }">
                  <Icon name="graph" :size="13" />
                </span>
                <span class="recent-name">{{ n.label }}</span>
                <span class="recent-time">{{ (n.createdAt || '').slice(5, 10) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.graph-page { display: flex; flex-direction: column; gap: 14px; }
.page-title { font-size: 18px; font-weight: 700; color: var(--text-primary); margin: 0; }

/* ---- 工具栏 ---- */
.graph-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; gap: 12px; }
.toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.toolbar-right { display: flex; align-items: center; gap: 8px; }
.g-search { position: relative; width: 260px; }
.g-input {
  width: 100%; height: 34px; padding: 0 34px 0 12px;
  border: 1px solid var(--border); border-radius: var(--radius-md); font-size: 13px;
}
.g-input:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); }
.g-search-icon { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); color: var(--text-tertiary); pointer-events: none; }
.g-select {
  height: 34px; padding: 0 28px 0 12px; font-size: 13px; font-family: inherit;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  background: var(--bg-surface); color: var(--text-primary); cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
}
.g-select:focus { outline: none; border-color: var(--brand); }
.g-reset { white-space: nowrap; }

/* ---- 图布主体 ---- */
.graph-body { display: grid; grid-template-columns: 1fr 300px; gap: 14px; min-height: 540px; }
.canvas-area { display: flex; flex-direction: column; overflow: hidden; padding: 0; position: relative; }
.canvas-state {
  margin: auto; text-align: center; color: var(--text-tertiary); max-width: 360px; padding: 24px;
}
.empty-avatar {
  width: 56px; height: 56px; border-radius: 50%; background: var(--brand-soft); color: var(--brand);
  display: flex; align-items: center; justify-content: center; margin: 0 auto 14px;
}
.empty-title { font-size: 16px; font-weight: 700; color: var(--text-primary); margin: 0 0 6px; }
.empty-sub { font-size: 13px; line-height: 1.6; margin: 0; }

.force-graph {
  width: 100%; flex: 1; min-height: 440px; cursor: grab; touch-action: none;
  background:
    radial-gradient(circle at 30% 40%, rgba(59, 130, 246, 0.04) 0%, transparent 50%),
    radial-gradient(circle at 70% 60%, rgba(16, 185, 129, 0.03) 0%, transparent 50%);
}
.force-graph:active { cursor: grabbing; }
.edge-label { font-size: 9px; font-weight: 500; fill: var(--text-tertiary); pointer-events: none; }
.gnode { cursor: pointer; }
.gnode circle { transition: stroke-width var(--dur-fast); }
.gnode .node-label {
  font-size: 9px; fill: var(--text-secondary); pointer-events: none; font-weight: 600;
  paint-order: stroke; stroke: var(--bg-surface); stroke-width: 3px; stroke-linejoin: round;
}
.gnode.dim, .edges .dim { opacity: 0.12; transition: opacity var(--dur-fast); }

.canvas-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; border-top: 1px solid var(--border); background: var(--bg-surface); flex-wrap: wrap; gap: 10px;
}
.zoom-controls { display: flex; align-items: center; gap: 4px; }
.zc-btn {
  width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: transparent; color: var(--text-secondary); cursor: pointer; font-family: inherit;
}
.zc-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.zoom-level { font-size: 12px; font-weight: 600; color: var(--text-primary); min-width: 42px; text-align: center; }
.legend { display: flex; align-items: center; gap: 14px; font-size: 11px; color: var(--text-secondary); flex-wrap: wrap; }
.leg-item { display: flex; align-items: center; gap: 4px; }
.leg-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.leg-divider { width: 1px; height: 14px; background: var(--border); }
.leg-line { display: inline-flex; align-items: center; gap: 4px; }
.leg-arrow { width: 20px; height: 0; border-top: 1.5px solid #94A3B8; position: relative; }
.leg-arrow::after { content: ''; position: absolute; right: -1px; top: -4px; border: 4px solid transparent; border-left: 4px solid #94A3B8; }
.canvas-hint { text-align: center; font-size: 11px; color: var(--text-placeholder); padding: 6px; margin: 0; }

/* ---- 右侧统计面板 ---- */
.stats-panel { padding: 16px; overflow-y: auto; }
.panel-head { display: flex; align-items: center; gap: 6px; margin-bottom: 14px; }
.panel-title { font-size: 15px; font-weight: 700; }
.info-hint { color: var(--text-tertiary); cursor: pointer; margin-left: auto; }

.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 18px; }
.stat-cell { display: flex; align-items: center; gap: 10px; padding: 10px; border-radius: var(--radius-md); background: var(--bg-subtle); }
.sc-icon-wrap { width: 36px; height: 36px; border-radius: 9px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.sc-label { font-size: 11px; color: var(--text-tertiary); }
.sc-value { font-size: 17px; font-weight: 800; letter-spacing: -0.01em; line-height: 1.2; }

.section-block { margin-bottom: 18px; }
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.section-title { font-size: 13px; font-weight: 700; color: var(--text-primary); }

.detail-box { padding: 12px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg-subtle); }
.detail-name { font-size: 14px; font-weight: 700; color: var(--text-primary); margin-bottom: 8px; }
.detail-meta { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.detail-tag { font-size: 11px; padding: 2px 8px; border-radius: var(--radius-pill); font-weight: 600; }
.detail-degree { font-size: 12px; color: var(--text-secondary); }
.detail-degree strong { color: var(--text-primary); }
.detail-neighbors { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.dn-label { font-size: 11px; color: var(--text-tertiary); }
.dn-chip { font-size: 11px; padding: 2px 8px; border-radius: var(--radius-pill); background: var(--bg-surface); border: 1px solid var(--border); color: var(--text-secondary); }

.type-bars { display: flex; flex-direction: column; gap: 7px; }
.type-bar { display: flex; align-items: center; gap: 8px; font-size: 11.5px; }
.tb-label { width: 56px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tb-track { flex: 1; height: 6px; border-radius: 3px; background: var(--bg-subtle); overflow: hidden; }
.tb-fill { display: block; height: 100%; border-radius: 3px; background: linear-gradient(90deg, var(--brand), #8B5CF6); }
.tb-count { width: 28px; text-align: right; color: var(--text-tertiary); }

.hot-list { display: flex; flex-direction: column; gap: 6px; }
.hot-item { display: flex; align-items: center; gap: 8px; padding: 7px 10px; border-radius: var(--radius-sm); transition: background var(--dur-fast); cursor: pointer; }
.hot-item:hover { background: var(--bg-hover); }
.hot-rank { width: 18px; height: 18px; border-radius: 4px; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; background: var(--bg-subtle); color: var(--text-tertiary); flex-shrink: 0; }
.hot-rank.top3 { background: var(--brand-soft); color: var(--brand); }
.hot-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.hot-name { font-size: 12.5px; color: var(--text-primary); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hot-count { font-size: 11px; color: var(--text-tertiary); white-space: nowrap; }
.hot-count strong { color: var(--text-secondary); }

.recent-list { display: flex; flex-direction: column; gap: 6px; }
.recent-item { display: flex; align-items: center; gap: 8px; padding: 7px 8px; border-radius: var(--radius-sm); transition: background var(--dur-fast); cursor: pointer; }
.recent-item:hover { background: var(--bg-hover); }
.recent-icon { width: 26px; height: 26px; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.recent-name { font-size: 12px; color: var(--text-primary); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.recent-time { font-size: 11px; color: var(--text-tertiary); white-space: nowrap; }

/* 加载动画 */
.canvas-state .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text-tertiary); display: inline-block; margin: 0 3px; animation: blink 1.2s infinite ease-in-out; }
.canvas-state .dot:nth-child(2) { animation-delay: 0.2s; }
.canvas-state .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.25; } 40% { opacity: 1; } }

/* ---- 节点管理 ---- */
.node-card { padding: 16px; }
.node-scroll { overflow-x: auto; }
.node-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.node-table th {
  text-align: left; padding: 10px 14px; background: var(--bg-subtle);
  color: var(--text-secondary); font-weight: 600; font-size: 12px;
  border-bottom: 1px solid var(--border);
}
.node-table td { padding: 10px 14px; border-bottom: 1px solid var(--border); color: var(--text-primary); }
.node-table tr:last-child td { border-bottom: none; }
.node-table tbody tr { cursor: pointer; transition: background var(--dur-fast); }
.node-table tbody tr:hover { background: var(--bg-hover); }
.col-name { font-weight: 600; }
.empty-hint { padding: 24px; text-align: center; color: var(--text-tertiary); font-size: 13px; }

/* ---- 关系检索 ---- */
.rel-card { padding: 16px; max-width: 760px; }
.rel-list { display: flex; flex-direction: column; gap: 8px; }
.rel-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 14px;
  border: 1px solid var(--border); border-radius: var(--radius-md); font-size: 13px;
}
.rel-src { font-weight: 600; color: var(--text-primary); }
.rel-arrow {
  padding: 2px 10px; border-radius: var(--radius-pill);
  background: var(--brand-soft); color: var(--brand); font-size: 12px; font-weight: 600;
}
.rel-tgt { color: var(--text-secondary); }

/* ---- 图谱统计 ---- */
.stats-page { display: flex; flex-direction: column; gap: 14px; }
.stat-grid.wide { grid-template-columns: repeat(4, 1fr); }
.stat-block { padding: 16px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

@media (max-width: 900px) {
  .stat-grid.wide { grid-template-columns: 1fr 1fr; }
  .grid-2 { grid-template-columns: 1fr; }
}
</style>
