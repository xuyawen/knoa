<script setup lang="ts">
// 知识图谱 — 全局图谱视图（力导向图 + 右侧数据面板）。
// 数据/筛选/派生统计来自 useGraphData；力导向布局与画布拖拽/缩放仅在本视图。
import { ref, computed, watch, nextTick } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import { useGraphData } from '@/composables/useGraphData'
import '@/assets/graph.css'
import type { GraphNode, GraphEdge } from '@/types/api'

const {
  graph, loading, searchTerm, selectedId, hoveredId,
  gFilterType, gFilterBiz, gFilterTime, nodeTypeOpts, bizCatOpts, timeRangeOpts,
  presentKbs, kbColor, nodeColor, kbName, degree,
  stats, docNodeCount, conceptCount, tagCount, bizCatCount,
  selectedNode, selectedNeighbors, typeBars, hotNodes, recentNodes,
  tx, ty, k, fetchGraph, onExport, resetAll, resetView,
} = useGraphData()

/* ---- 力导向布局 ---- */
interface LNode { id: string; x: number; y: number; deg: number; r: number }
const W = 900
const H = 560
const lNodes = ref<LNode[]>([])
const svgRef = ref<SVGSVGElement | null>(null)

const degreeLocal = degree // 别名，保持模板可读

function computeLayout(nodes: GraphNode[], edges: GraphEdge[]): LNode[] {
  const n = nodes.length
  const arr: LNode[] = nodes.map((nd, i) => {
    const ang = (i / Math.max(1, n)) * Math.PI * 2
    const rad = Math.min(W, H) * 0.4
    return {
      id: nd.id,
      x: W / 2 + Math.cos(ang) * rad,
      y: H / 2 + Math.sin(ang) * rad,
      deg: degreeLocal.value[nd.id] || 0,
      r: 6 + Math.min(13, Math.sqrt(degreeLocal.value[nd.id] || 0) * 3),
    }
  })
  const idx: Record<string, number> = {}
  arr.forEach((a, i) => { idx[a.id] = i })

  const REP = 6000
  const SPRING = 0.04
  const REST = 72
  const CENTER = 0.008
  for (let it = 0; it < 240; it++) {
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

// 数据变化（首次加载 / 筛选切换）后重算布局
watch(graph, async (g) => {
  if (!g) return
  lNodes.value = computeLayout(g.nodes, g.edges)
  await nextTick()
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
    return null
  }
  if (set.size) {
    const extra: string[] = []
    for (const id of set) for (const nb of (degreeLocal.value[id] !== undefined ? adjacencySet(id) : [])) extra.push(nb)
    extra.forEach((x) => set.add(x))
  }
  return set
})
// 仅用于高亮邻居展开
function adjacencySet(id: string): string[] {
  const out: string[] = []
  for (const e of graph.value?.edges || []) {
    if (e.source === id) out.push(e.target)
    else if (e.target === id) out.push(e.source)
  }
  return out
}
function nodeDim(id: string): boolean {
  const a = activeIds.value
  return a ? !a.has(id) : false
}
function edgeDim(e: GraphEdge): boolean {
  const a = activeIds.value
  if (!a) return false
  return !(a.has(e.source) && a.has(e.target))
}

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
</script>

<template>
  <div class="graph-page">
    <!-- ====== 工具栏 ====== -->
    <div class="graph-toolbar card">
      <div class="toolbar-left">
        <div class="g-search">
          <input v-model="searchTerm" type="text" placeholder="请输入关键词搜索图谱…" class="g-input" />
          <Icon name="search" :size="15" class="g-search-icon" />
        </div>
        <CustomSelect v-model="gFilterType" :options="nodeTypeOpts" placeholder="节点类型" width="105px" />
        <CustomSelect v-model="gFilterBiz" :options="bizCatOpts" placeholder="业务分类" width="110px" />
        <CustomSelect v-model="gFilterTime" :options="timeRangeOpts" placeholder="创建时间" width="115px" />
        <button class="btn btn-ghost btn-sm g-reset" @click="resetAll">重置</button>
      </div>
      <div class="toolbar-right">
        <button class="btn btn-primary btn-sm" :disabled="loading" @click="fetchGraph">
          <Icon name="search" :size="13" /> 搜索
        </button>
        <button class="btn btn-outline btn-sm" title="导出图谱" @click="onExport">
          <Icon name="download" :size="13" /> 导出图谱
        </button>
      </div>
    </div>

    <!-- ====== 主区：图布 + 右侧面板 ====== -->
    <div class="graph-body">
      <!-- 左：图布 -->
      <div class="canvas-area card">
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
              <path d="M0,0 L0,6 L8,3 z" fill="var(--text-tertiary)" />
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

        <div v-if="graph && graph.nodes.length" class="graph-legend">
          <span class="leg-item"><i class="leg-dot" style="background:var(--accent-blue)"></i> 文档</span>
          <span class="leg-item"><i class="leg-dot" style="background:var(--accent-green)"></i> 知识点</span>
          <span class="leg-item"><i class="leg-dot" style="background:var(--accent-violet)"></i> 标签</span>
          <span class="leg-item"><i class="leg-dot" style="background:var(--accent-amber)"></i> 业务分类</span>
          <span class="leg-divider"></span>
          <span class="leg-item leg-line"><i class="leg-line-dash" style="border-color:var(--text-tertiary)"></i> 关联</span>
          <span class="leg-item leg-line"><i class="leg-line-solid" style="border-color:var(--accent-blue)"></i> 引用</span>
          <span class="leg-item leg-line"><i class="leg-line-solid" style="border-color:var(--accent-green)"></i> 包含</span>
        </div>
      </div>

      <!-- 右：数据面板 -->
      <aside class="stats-panel card">
        <div class="panel-head">
          <span class="panel-title">图谱数据统计</span>
          <Icon name="graph" :size="14" class="info-hint" />
        </div>

        <div class="stat-grid">
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:var(--accent-blue-soft)"><Icon name="graph" :size="18" style="color:var(--accent-blue)"/></div>
            <div class="sc-info"><div class="sc-label">节点总数</div><div class="sc-value" style="color:var(--accent-blue)">{{ stats?.nodeCount ?? 0 }}</div></div>
          </div>
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:var(--accent-green-soft)"><Icon name="link" :size="18" style="color:var(--accent-green)"/></div>
            <div class="sc-info"><div class="sc-label">关系总数</div><div class="sc-value" style="color:var(--accent-green)">{{ stats?.edgeCount ?? 0 }}</div></div>
          </div>
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:var(--accent-blue-soft)"><Icon name="doc" :size="18" style="color:var(--accent-blue)"/></div>
            <div class="sc-info"><div class="sc-label">文档节点</div><div class="sc-value" style="color:var(--accent-blue)">{{ docNodeCount }}</div></div>
          </div>
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:var(--accent-green-soft)"><Icon name="lightbulb" :size="18" style="color:var(--accent-green)"/></div>
            <div class="sc-info"><div class="sc-label">知识点</div><div class="sc-value" style="color:var(--accent-green)">{{ conceptCount }}</div></div>
          </div>
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:var(--accent-violet-soft)"><Icon name="tag" :size="18" style="color:var(--accent-violet)"/></div>
            <div class="sc-info"><div class="sc-label">标签</div><div class="sc-value" style="color:var(--accent-violet)">{{ tagCount }}</div></div>
          </div>
          <div class="stat-cell">
            <div class="sc-icon-wrap" style="background:var(--accent-amber-soft)"><Icon name="folder" :size="18" style="color:var(--accent-amber)"/></div>
            <div class="sc-info"><div class="sc-label">业务分类</div><div class="sc-value" style="color:var(--accent-amber)">{{ bizCatCount }}</div></div>
          </div>
        </div>

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

        <div class="section-block">
          <div class="section-title">热门知识点 Top 5</div>
          <div class="hot-list">
            <div v-for="(item, i) in hotNodes" :key="item.id" class="hot-item" @click="selectedId = item.id" @mouseenter="hoveredId = item.id" @mouseleave="hoveredId = null">
              <span class="hot-rank" :class="{ top3: i < 3 }">{{ i + 1 }}</span>
              <span class="hot-dot" :style="{ background: nodeColor(item.kbId) }"></span>
              <span class="hot-name">{{ item.label }}</span>
              <span class="hot-count">度数 <strong>{{ item.degree }}</strong></span>
            </div>
          </div>
        </div>

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
  </div>
</template>
