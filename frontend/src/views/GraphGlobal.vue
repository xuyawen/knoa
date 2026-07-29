<script setup lang="ts">
// 知识图谱 — 全局图谱视图（力导向图 + 右侧数据面板）。
// 数据/筛选/派生统计来自 useGraphData；力导向布局与画布拖拽/缩放仅在本视图。
import { ref, shallowRef, triggerRef, computed, watch, nextTick, onUnmounted } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import { useGraphData, downloadBlob, dateStamp } from '@/composables/useGraphData'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { useBackdropClick } from '@/composables/useBackdropClick'
import '@/assets/graph.css'
import '@/assets/dashboard.css'
import type { GraphNode, GraphEdge } from '@/types/api'

const knowledge = useKnowledgeStore()
const toast = useToastStore()

const {
  graph, loading, searchTerm, selectedId, hoveredId, selectedKb,
  gFilterType, gFilterBiz, gFilterTime, nodeTypeOpts, bizCatOpts, timeRangeOpts,
  presentKbs, kbColor, nodeColor, kbName, degree, adjacency, nodeById,
  typeColor, typeColorMap,
  stats, maxDegree, avgDegree,
  selectedNode, selectedNeighbors, typeBars, hotNodes, recentNodes,
  tx, ty, k, fetchGraph, exportRemote, exportCSV, resetAll,
  sourceInfo, sourceLoading, loadSource, removeNode,
  rebuild, rebuilding, rebuildProgress, resumeRebuildIfRunning, gapSignals, loadGaps,
  focusNodeId, focusedNodeIds, enterFocus, exitFocus,
} = useGraphData()

/* ---- 源文档弹窗 ---- */
const sourceModalVisible = ref(false)
const sourceBd = useBackdropClick(() => { sourceModalVisible.value = false })

/* ---- 导出菜单 ---- */
const exportOpen = ref(false)
const exportMenuPos = ref({ top: 0, right: 0 })
function toggleExportMenu(e: MouseEvent) {
  if (exportOpen.value) {
    exportOpen.value = false
    return
  }
  // 画布卡片 overflow:hidden 会裁剪绝对定位子元素，
  // 故菜单 Teleport 到 body + 视口坐标定位
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  exportMenuPos.value = { top: rect.bottom + 6, right: window.innerWidth - rect.right }
  exportOpen.value = true
}

type ExportKind = 'png' | 'csv-nodes' | 'csv-edges' | 'gexf' | 'json'
async function doExport(kind: ExportKind) {
  exportOpen.value = false
  try {
    if (kind === 'png') await exportPNG()
    else if (kind === 'csv-nodes') exportCSV('nodes')
    else if (kind === 'csv-edges') exportCSV('edges')
    else await exportRemote(kind)
  } catch (err: unknown) {
    toast.error(`导出失败：${errMsg(err)}`)
  }
}

/** 导出 PNG：当前画布 SVG 序列化 → 离屏 canvas 渲染 → 下载。
 * 注意：canvas 渲染 SVG 不读外部 CSS，文本的颜色/字号必须内联到克隆节点上。 */
async function exportPNG() {
  const svg = svgRef.value
  if (!svg) throw new Error('画布未就绪')
  const clone = svg.cloneNode(true) as SVGSVGElement
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  clone.setAttribute('width', String(canvasW.value * 2))
  clone.setAttribute('height', String(canvasH.value * 2))
  const srcTexts = svg.querySelectorAll('text')
  const cloneTexts = clone.querySelectorAll('text')
  srcTexts.forEach((t, i) => {
    const cs = getComputedStyle(t)
    cloneTexts[i].setAttribute(
      'style',
      `fill:${cs.fill};font-size:${cs.fontSize};font-family:${cs.fontFamily};font-weight:${cs.fontWeight};`,
    )
  })
  const xml = new XMLSerializer().serializeToString(clone)
  const svgUrl = URL.createObjectURL(new Blob([xml], { type: 'image/svg+xml;charset=utf-8' }))
  try {
    const img = new Image()
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('SVG 渲染失败'))
      img.src = svgUrl
    })
    const canvas = document.createElement('canvas')
    canvas.width = canvasW.value * 2
    canvas.height = canvasH.value * 2
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas 上下文不可用')
    // SVG 本身透明：铺上画布区背景色，避免导出图片背景透明
    const bg = getComputedStyle(svg.parentElement || svg).backgroundColor
    ctx.fillStyle = bg && bg !== 'rgba(0, 0, 0, 0)' ? bg : '#0B1220'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
    if (!blob) throw new Error('PNG 编码失败')
    downloadBlob(blob, `graph-${dateStamp()}.png`)
  } finally {
    URL.revokeObjectURL(svgUrl)
  }
}

/* ---- 力导向布局 ---- */
interface LNode { id: string; x: number; y: number; r: number }
// 画布坐标系尺寸：动态跟随 svg 元素实际尺寸（见下方 ResizeObserver）。
// 固定 viewBox 在与自身纵横比不符的容器里会被 meet 缩放成中间一条、上下留大片空边
const canvasW = ref(1100)
const canvasH = ref(680)
// shallowRef：坐标是高频变更热点，绕过深代理；交互结束时手动 triggerRef 一次性触发渲染
const lNodes = shallowRef<LNode[]>([])
const svgRef = ref<SVGSVGElement | null>(null)
const rootRef = ref<SVGGElement | null>(null)
const zoomLabelRef = ref<HTMLElement | null>(null)

function computeLayout(nodes: GraphNode[], edges: GraphEdge[]): LNode[] {
  const n = nodes.length
  const W = canvasW.value
  const H = canvasH.value
  // 初始位置按度数分层：高度数节点近中心、低度数节点分布外环
  // （黄金角螺线 + sqrt 径向分布保证密度均匀），给力导向模拟更好的初始结构，
  // 收敛结果比随机环布边交叉显著更少、更不容易缠成发丝球
  const ranks: number[] = new Array(n).fill(0)
  nodes
    .map((nd, i) => ({ i, deg: degree.value[nd.id] || 0 }))
    .sort((a, b) => b.deg - a.deg)
    .forEach((s, r) => { ranks[s.i] = r })
  const GOLDEN = 2.399963229728653
  // 类型聚类锚点：给每个实体类型分配一个黄金螺线上的锚位（大类靠中心），
  // 模拟时节点被轻柔拉向所属类型的锚点 → 同类节点聚群、颜色形成有意义的分组，
  // 消除「彩色糖豆随机撒」的观感
  const typeLabels = typeBars.value.map((t) => t.label) // 已按节点数降序
  const K = typeLabels.length
  const anchors: Record<string, { x: number; y: number }> = {}
  typeLabels.forEach((t, i) => {
    const frac = K <= 1 ? 0 : i / (K - 1)
    const ang = i * GOLDEN
    const rho = Math.sqrt(frac)
    // 椭圆分布（按画布实际纵横比拉伸）：填满上下左右空条，
    // 四角天然留空——圆形锚布在宽画布里两侧会剩出大片空白
    anchors[t] = {
      x: W / 2 + Math.cos(ang) * (40 + rho * (W / 2 - 110)),
      y: H / 2 + Math.sin(ang) * (40 + rho * (H / 2 - 110)),
    }
  })
  const TYPE_PULL = 0.008
  // 软边界：超出留白边距后施加与超出量成正比的向内回复力。
  // 与逐轮硬夹不同（不会形成点墙）：节点按受力平衡停在边界附近不同距离上，形态有机
  const BM = 45
  const BOUND = 0.08
  const arr: LNode[] = nodes.map((nd, i) => {
    const deg = degree.value[nd.id] || 0
    const frac = n <= 1 ? 0 : ranks[i] / (n - 1)
    const ang = ranks[i] * GOLDEN + Math.random() * 0.3
    const spread = Math.sqrt(frac) * (0.9 + Math.random() * 0.2)
    return {
      id: nd.id,
      x: W / 2 + Math.cos(ang) * (30 + spread * (W / 2 - 90)),
      y: H / 2 + Math.sin(ang) * (30 + spread * (H / 2 - 90)),
      r: 6 + Math.min(19, Math.sqrt(deg) * 4.6),
    }
  })
  const idx: Record<string, number> = {}
  arr.forEach((a, i) => { idx[a.id] = i })

  // 参数随节点数缩放：节点越多，斥力/间距越大，避免挤成一团
  const scale = Math.max(1, Math.sqrt(n / 30))
  const REP = 12000 * scale * scale
  // 斥力截断：力衰减到 0.4 以下的节点对直接跳过 sqrt（碰撞距离~50 远小于截断半径，不会漏检）。
  // 图谱尺度下多数节点对距离远超截断，可省掉大半 sqrt/min 计算
  const REP_CUTOFF_D2 = REP / 0.4
  const SPRING = 0.035
  const REST = 110 * scale
  const CENTER = 0.006 / scale
  const iterations = n > 250 ? 120 : n > 120 ? 180 : 280
  const fxArr = new Float64Array(n)
  const fyArr = new Float64Array(n)
  for (let it = 0; it < iterations; it++) {
    fxArr.fill(0); fyArr.fill(0)
    // 斥力（库仑）+ 碰撞分离：合并到同一个 O(n²) 对循环，
    // 省掉一整趟成对遍历与每对一次 sqrt（布局耗时约减 1/3）
    for (let i = 0; i < n; i++) {
      const ri = arr[i].r
      for (let j = i + 1; j < n; j++) {
        const dx = arr[i].x - arr[j].x
        const dy = arr[i].y - arr[j].y
        const d2 = dx * dx + dy * dy + 0.01
        if (d2 > REP_CUTOFF_D2) continue
        const d = Math.sqrt(d2)
        // 斥力封顶：初始几乎重合的节点对 d2≈0.01 会产生天文数字斥力，
        // 把节点炸飞到远处（撑大 fitView 包围盒 → 整图缩到 30%）
        const f = Math.min(REP / d2, 60)
        let fx = (dx / d) * f
        let fy = (dy / d) * f
        // 碰撞：强制推开重叠节点（半径 + 标签空间）
        const minDist = ri + arr[j].r + 28
        if (d < minDist) {
          const push = (minDist - d) / d * 0.5
          fx += dx * push
          fy += dy * push
        }
        fxArr[i] += fx; fyArr[i] += fy
        fxArr[j] -= fx; fyArr[j] -= fy
      }
    }
    // 弹簧（胡克）
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
      fxArr[a] += fx; fyArr[a] += fy
      fxArr[b] -= fx; fyArr[b] -= fy
    }
    // 应用合力：位移上限 + 模拟退火冷却（防止初始密集时“爆炸”飞出视野）
    const maxDisp = 12 + 60 * (1 - it / iterations)
    for (let i = 0; i < n; i++) {
      fxArr[i] += (W / 2 - arr[i].x) * CENTER
      fyArr[i] += (H / 2 - arr[i].y) * CENTER
      // 类型聚类：向所属类型锚点的轻柔拉力（软聚类，不压倒弹簧/斥力）
      const anchor = anchors[nodes[i].type || '']
      if (anchor) {
        fxArr[i] += (anchor.x - arr[i].x) * TYPE_PULL
        fyArr[i] += (anchor.y - arr[i].y) * TYPE_PULL
      }
      // 软边界：防止斥力把节点推出画布——布局不超出画布，
      // 归一化就只需轻柔放大，不会触发「压缩 → 碰撞反撑大 → fitView 缩出空边」的拉锯
      if (arr[i].x < BM) fxArr[i] += (BM - arr[i].x) * BOUND
      else if (arr[i].x > W - BM) fxArr[i] -= (arr[i].x - (W - BM)) * BOUND
      if (arr[i].y < BM) fyArr[i] += (BM - arr[i].y) * BOUND
      else if (arr[i].y > H - BM) fyArr[i] -= (arr[i].y - (H - BM)) * BOUND
      const len = Math.sqrt(fxArr[i] * fxArr[i] + fyArr[i] * fyArr[i]) || 1
      const cap = Math.min(1, maxDisp / len)
      arr[i].x += fxArr[i] * cap
      arr[i].y += fyArr[i] * cap
    }
  }
  // 布局归一化：横纵独立伸缩填满画布可用区。力布局的自然平衡态偏圆团，
  // 而画布不一定是正方形——等比缩放修不了纵横比失配；按轴拉伸才能填满空条。
  // 软边界已保证模拟结果不超出画布，这里基本只是轻柔放大；
  // 包围盒下限 150 防极少节点时极端拉伸，放大封顶 2.5×
  const PAD = 40
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const nd of arr) {
    minX = Math.min(minX, nd.x); maxX = Math.max(maxX, nd.x)
    minY = Math.min(minY, nd.y); maxY = Math.max(maxY, nd.y)
  }
  const bw = Math.max(maxX - minX, 150)
  const bh = Math.max(maxY - minY, 150)
  const sx = Math.min((W - PAD * 2) / bw, 2.5)
  const sy = Math.min((H - PAD * 2) / bh, 2.5)
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  for (const nd of arr) {
    nd.x = W / 2 + (nd.x - cx) * sx
    nd.y = H / 2 + (nd.y - cy) * sy
  }
  // 归一化后重叠分离：位置被等比压缩但节点半径不缩放，
  // 模拟时留的间隙可能被压到小于半径和 → 节点重叠、无法点选。
  // 在最终尺度上补几轮碰撞分离，保证每个节点独立可选
  for (let pass = 0; pass < 40; pass++) {
    let moved = false
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const dx = arr[j].x - arr[i].x
        const dy = arr[j].y - arr[i].y
        const minDist = arr[i].r + arr[j].r + 12
        const d2 = dx * dx + dy * dy
        if (d2 > minDist * minDist) continue // 远距离对不可能重叠，跳过 sqrt（图谱尺度下 95%+ 的节点对）
        const d = Math.sqrt(d2) + 0.01
        if (d < minDist) {
          const push = (minDist - d) / d * 0.5
          arr[i].x -= dx * push; arr[i].y -= dy * push
          arr[j].x += dx * push; arr[j].y += dy * push
          moved = true
        }
      }
    }
    if (!moved) break
  }
  return arr
}

/** 边的二次贝塞尔曲线 / 标签位置：模板渲染与拖拽时直接更新 DOM 共用同一套公式，必须保持一致 */
function edgePathD(sx: number, sy: number, ex: number, ey: number): string {
  return `M${sx},${sy} Q${(sx + ex) / 2 + (ey - sy) * 0.12},${(sy + ey) / 2 - (ex - sx) * 0.12} ${ex},${ey}`
}
function edgeLabelX(sx: number, sy: number, ex: number, ey: number): number {
  return (sx + ex) / 2 + (ey - sy) * 0.06
}
function edgeLabelY(sx: number, sy: number, ex: number, ey: number): number {
  return (sy + ey) / 2 - (ex - sx) * 0.06 - 4
}

const posMap = computed<Record<string, { x: number; y: number }>>(() => {
  const m: Record<string, { x: number; y: number }> = {}
  for (const n of lNodes.value) m[n.id] = { x: n.x, y: n.y }
  return m
})

// 渲染几何预计算：path/label 坐标串只在布局变化时构建一次（posMap 派生）。
// 悬浮/选中等高频状态变化不再重建 406 条边的 d 串与 347 个节点的 transform 串
const edgeRender = computed(() => {
  const m = posMap.value
  return (graph.value?.edges || []).map((e) => {
    const s = m[e.source]
    const t = m[e.target]
    if (!s || !t) return null
    return {
      d: edgePathD(s.x, s.y, t.x, t.y),
      lx: edgeLabelX(s.x, s.y, t.x, t.y),
      ly: edgeLabelY(s.x, s.y, t.x, t.y),
    }
  })
})
const nodeRender = computed(() =>
  lNodes.value.map((n) => {
    const meta = nodeById.value[n.id]
    return { tf: `translate(${n.x},${n.y})`, fill: typeColor(meta?.type), label: meta?.label }
  })
)

/** 自动缩放平移，让所有节点尽可能铺满画布（只留最小安全边距） */
function fitView() {
  cancelZoomCommit()
  const arr = lNodes.value
  if (!arr.length) return
  const W = canvasW.value
  const H = canvasH.value
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const nd of arr) {
    // 边距只留安全量：横向给标签留 r+16，顶部 r+10，底部 r+26（标签在节点下方延伸约 r+25）
    minX = Math.min(minX, nd.x - nd.r - 16)
    maxX = Math.max(maxX, nd.x + nd.r + 16)
    minY = Math.min(minY, nd.y - nd.r - 10)
    maxY = Math.max(maxY, nd.y + nd.r + 26)
  }
  const bw = maxX - minX || 1
  const bh = maxY - minY || 1
  // 以前 PAD=50 + 每节点 r+20 把适配缩放压到 88%，画布四周空边明显；
  // 图例/缩放栏在 svg 外部下方（不占 viewBox），只需留画布内最小边距
  const availW = W - 40
  const availH = H - 28
  const fitK = Math.min(availW / bw, availH / bh)
  k.value = Math.min(3, Math.max(0.05, fitK))
  tx.value = 20 + (availW - k.value * bw) / 2 - k.value * minX
  ty.value = 14 + (availH - k.value * bh) / 2 - k.value * minY
}

// 数据变化（首次加载 / 筛选切换）后重算布局；immediate 保证从其他图谱 tab 切回时
// （共享状态已有数据、watch 不会再触发）也能立即布局，避免画布空白
watch(graph, async (g) => {
  if (!g) return
  lNodes.value = computeLayout(g.nodes, g.edges)
  fitView()
  void loadGaps()
  await nextTick()
}, { immediate: true })

// viewBox 动态跟随 svg 元素实际尺寸：canvas-area 高度由右侧面板撑开，
// 固定 viewBox（1100×680）在纵横比不符的容器里会被 meet 缩放成中间一条、上下留大片空边。
// viewBox 与元素同宽高比后，布局按屏幕实际形状填满，letterbox 空边彻底消失
let resizeRO: ResizeObserver | null = null
let resizeTimer: ReturnType<typeof setTimeout> | null = null
watch(svgRef, (el) => {
  resizeRO?.disconnect()
  resizeRO = null
  if (!el) return
  resizeRO = new ResizeObserver((entries) => {
    const r = entries[0]?.contentRect
    if (!r) return
    const nw = Math.round(r.width)
    const nh = Math.round(r.height)
    if (nw < 100 || nh < 100) return
    // 忽略微小波动；尺寸真变化才重算布局（防抖，避免拖窗口时连续重算）
    if (Math.abs(nw - canvasW.value) < 24 && Math.abs(nh - canvasH.value) < 24) return
    if (resizeTimer) clearTimeout(resizeTimer)
    resizeTimer = setTimeout(() => {
      canvasW.value = nw
      canvasH.value = nh
      const g = graph.value
      if (g && g.nodes.length) {
        lNodes.value = computeLayout(g.nodes, g.edges)
        fitView()
      }
    }, 180)
  })
  resizeRO.observe(el)
}, { immediate: true })

// 进入页面 / 切换知识库时，若该库仍在后台重建（如刷新后），恢复进度横幅 + 轮询
watch(() => gFilterBiz.value || selectedKb.value, (kb) => {
  if (kb) void resumeRebuildIfRunning(kb)
}, { immediate: true })

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
    // 展开一跳邻居（复用共享邻接表索引，避免逐 id 扫全边集）
    for (const id of [...set]) {
      for (const nb of adjacency.value[id] || []) set.add(nb)
    }
  }
  return set
})
// dim 状态预计算：悬浮/选中/搜索/图例透镜任一变化时一次性算出全量标记，
// 模板只读数组/Map——不再逐元素调函数（原先每条边在一轮渲染里调 3 次 edgeDim）
const dimState = computed(() => {
  const lt = legendHoverType.value
  const a = activeIds.value
  const nb = nodeById.value
  const ns = graph.value?.nodes || []
  const es = graph.value?.edges || []
  const nodes = new Map<string, boolean>()
  const edges: boolean[] = new Array(es.length)
  if (lt) {
    for (const n of ns) nodes.set(n.id, nb[n.id]?.type !== lt)
    for (let i = 0; i < es.length; i++) edges[i] = nb[es[i].source]?.type !== lt || nb[es[i].target]?.type !== lt
  } else if (a) {
    for (const n of ns) nodes.set(n.id, !a.has(n.id))
    for (let i = 0; i < es.length; i++) edges[i] = !(a.has(es[i].source) && a.has(es[i].target))
  } else {
    edges.fill(false)
  }
  return { nodes, edges }
})
// 边标签降噪：有焦点时只显示焦点相关边，无焦点时边少才全显
function edgeLabelShown(i: number, e: GraphEdge): boolean {
  if (dimState.value.edges[i]) return false
  const f = focusId.value
  if (f) return e.source === f || e.target === f
  return (graph.value?.edges.length || 0) <= 60
}
// 悬浮合并：快速掠过多个节点时 rAF 内只取最后一次，避免逐节点触发整树渲染
let hoverRaf = 0
function setHover(id: string | null) {
  if (hoverRaf) cancelAnimationFrame(hoverRaf)
  hoverRaf = requestAnimationFrame(() => { hoverRaf = 0; hoveredId.value = id })
}

// 节点标签语义缩放：总览时只显示高度数 hub 节点的名字，随缩放增大逐步显示全部；
// 避免几十个小标签在低缩放率下糊成一片。k.value 在缩放结束后才提交（120ms 防抖），
// 标签随之“落定后更新”，避免连续缩放期间逐帧抖动。
const labelDegThreshold = computed(() => {
  const kv = k.value
  if (kv >= 1.5) return 0
  if (kv >= 1.1) return 2
  if (kv >= 0.75) return 5
  return 8
})
function nodeLabelShown(id: string): boolean {
  // 搜索命中 / 悬浮 / 选中及其邻居：标签始终可见
  if (activeIds.value?.has(id)) return true
  return (degree.value[id] || 0) >= labelDegThreshold.value
}

/* ---- 图例：LLM 抽取的实体类型动辄几十种，全平铺是“文字墙”。
 * 默认只展示节点数 Top N 的类型（带计数），其余收进「更多」；
 * 悬浮某类型时画布上只高亮该类型节点，图例即探索透镜。 ---- */
const legendExpanded = ref(false)
const legendHoverType = ref<string | null>(null)
const LEGEND_COLLAPSED_COUNT = 10
const visibleLegendTypes = computed(() =>
  legendExpanded.value ? typeBars.value : typeBars.value.slice(0, LEGEND_COLLAPSED_COUNT)
)
const hiddenTypeCount = computed(() => Math.max(0, typeBars.value.length - LEGEND_COLLAPSED_COUNT))

/* ---- 交互：平移 / 拖拽 / 缩放 ----
 * 性能：原先每次 pointermove 都触发整棵 SVG（节点+边+标签，数百个元素）的全量 diff；
 * 现改为 rAF 合并 + 直接写 DOM——平移/缩放只更新根 <g> 的 transform（O(1)），
 * 节点拖拽只更新该节点与相连边（O(度数)）；交互结束再提交回共享 ref，触发一次校准渲染。
 */
let panning = false
let dragging: string | null = null
let lastRoot: { x: number; y: number } | null = null
// 交互期间的本地视图状态（watcher 与共享 tx/ty/k 同步，交互结束时提交回去）
let viewTx = 0
let viewTy = 0
let viewK = 1
let rafId = 0
let pendingPointer: { x: number; y: number } | null = null
let pendingZoom: number | null = null
let zoomCommitTimer: ReturnType<typeof setTimeout> | null = null
// 节点拖拽：按下时一次性收集被拖节点 DOM 与相连边的元素，之后每帧只更新它们
let dragEl: SVGGElement | null = null
let dragPos: { x: number; y: number } | null = null
let dragEdgeEls: { path: SVGPathElement; label: SVGTextElement | null; e: GraphEdge }[] = []

// 共享视图状态的外部变更（fitView / 缩放按钮）同步到本地镜像
watch([tx, ty, k], () => {
  viewTx = tx.value; viewTy = ty.value; viewK = k.value
}, { immediate: true })

function cancelZoomCommit() {
  if (zoomCommitTimer) { clearTimeout(zoomCommitTimer); zoomCommitTimer = null }
  pendingZoom = null
}
onUnmounted(() => {
  if (rafId) cancelAnimationFrame(rafId)
  if (hoverRaf) cancelAnimationFrame(hoverRaf)
  cancelZoomCommit()
  resizeRO?.disconnect()
  if (resizeTimer) clearTimeout(resizeTimer)
})

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
  return { x: (r.x - viewTx) / viewK, y: (r.y - viewTy) / viewK }
}
function writeViewTransform() {
  rootRef.value?.setAttribute('transform', `translate(${viewTx},${viewTy}) scale(${viewK})`)
}
function scheduleFrame() {
  if (!rafId) rafId = requestAnimationFrame(applyFrame)
}
function applyFrame() {
  rafId = 0
  if (pendingZoom !== null) {
    viewK = pendingZoom
    pendingZoom = null
    writeViewTransform()
    if (zoomLabelRef.value) zoomLabelRef.value.textContent = `${Math.round(viewK * 100)}%`
    // 防抖提交：滚轮连击结束后再共享 k（触发一次渲染，校准插值绑定）
    if (zoomCommitTimer) clearTimeout(zoomCommitTimer)
    zoomCommitTimer = setTimeout(() => { zoomCommitTimer = null; k.value = viewK }, 120)
  }
  if (pendingPointer) {
    const p = pendingPointer
    pendingPointer = null
    if (dragging && dragEl && dragPos) {
      const l = toLocal(p.x, p.y)
      dragPos.x = l.x
      dragPos.y = l.y
      dragEl.setAttribute('transform', `translate(${l.x},${l.y})`)
      for (const { path, label, e } of dragEdgeEls) {
        const other = e.source === dragging ? e.target : e.source
        const op = posMap.value[other]
        if (!op) continue
        const sx = e.source === dragging ? l.x : op.x
        const sy = e.source === dragging ? l.y : op.y
        const ex = e.target === dragging ? l.x : op.x
        const ey = e.target === dragging ? l.y : op.y
        path.setAttribute('d', edgePathD(sx, sy, ex, ey))
        if (label) {
          label.setAttribute('x', String(edgeLabelX(sx, sy, ex, ey)))
          label.setAttribute('y', String(edgeLabelY(sx, sy, ex, ey)))
        }
      }
    } else if (panning && lastRoot) {
      const r = toRoot(p.x, p.y)
      viewTx += r.x - lastRoot.x
      viewTy += r.y - lastRoot.y
      lastRoot = r
      writeViewTransform()
    }
  }
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
  dragEl = e.currentTarget as SVGGElement
  const nd = lNodes.value.find((x) => x.id === id)
  dragPos = nd ? { x: nd.x, y: nd.y } : null
  // 一次性收集相连边的 DOM 元素（之后每帧更新是 O(度数)，绕过全树 diff）
  dragEdgeEls = []
  const edges = graph.value?.edges || []
  const edgesG = svgRef.value?.querySelector('g.edges')
  if (edgesG) {
    for (const child of Array.from(edgesG.children)) {
      const ed = edges[Number((child as SVGGElement).dataset.i)]
      if (!ed || (ed.source !== id && ed.target !== id)) continue
      const path = child.querySelector('path')
      if (path) dragEdgeEls.push({ path, label: child.querySelector('text'), e: ed })
    }
  }
  ;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
}
function onMove(e: PointerEvent) {
  if (!dragging && !panning) return
  pendingPointer = { x: e.clientX, y: e.clientY }
  scheduleFrame()
}
function onUp() {
  // 松手时先应用最后一帧未处理的指针位置，再提交回共享状态（触发一次渲染）
  if (rafId) { cancelAnimationFrame(rafId); rafId = 0; applyFrame() }
  if (dragging && dragPos) {
    const nd = lNodes.value.find((x) => x.id === dragging)
    if (nd) { nd.x = dragPos.x; nd.y = dragPos.y; triggerRef(lNodes) }
  }
  if (panning) { tx.value = viewTx; ty.value = viewTy }
  panning = false
  dragging = null
  dragEl = null
  dragPos = null
  dragEdgeEls = []
}
function onWheel(e: WheelEvent) {
  // 模板 @wheel.prevent 已阻止默认滚动
  const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
  pendingZoom = Math.min(3, Math.max(0.3, (pendingZoom ?? viewK) * factor))
  scheduleFrame()
}
function zoom(dir: number) {
  cancelZoomCommit()
  k.value = Math.min(3, Math.max(0.3, k.value * (dir > 0 ? 1.2 : 1 / 1.2)))
}

/* ---- 重建图谱弹窗 ---- */
const rebuildVisible = ref(false)
const rebuildBd = useBackdropClick(() => { rebuildVisible.value = false })
const rebuildKb = ref('')
const rebuildClean = ref(false)
const kbRebuildOpts = computed(() => knowledge.bases.map(b => ({ label: b.name, value: b.id })))
function openRebuild() {
  // 默认选中当前筛选库（若有）
  rebuildKb.value = selectedKb.value || ''
  rebuildClean.value = false
  rebuildVisible.value = true
}
function confirmRebuild() {
  if (!rebuildKb.value) return
  rebuildVisible.value = false
  void rebuild(rebuildKb.value, rebuildClean.value)
}
</script>

<template>
  <div class="graph-page">
    <!-- ====== 工具栏 ====== -->
    <div class="graph-toolbar card">
      <div class="toolbar-left">
        <CustomSelect v-model="gFilterBiz" :options="bizCatOpts" placeholder="知识库" width="140px" />
        <div class="g-search">
          <input v-model="searchTerm" type="text" placeholder="请输入关键词搜索图谱…" class="g-input" />
          <Icon name="search" :size="15" class="g-search-icon" />
        </div>
        <CustomSelect v-model="gFilterType" :options="nodeTypeOpts" placeholder="节点类型" width="105px" />
        <CustomSelect v-model="gFilterTime" :options="timeRangeOpts" placeholder="创建时间" width="115px" />
        <button class="btn btn-ghost btn-sm g-reset" @click="resetAll">重置</button>
        <button class="btn btn-primary btn-sm" :disabled="loading" @click="fetchGraph">
          <Icon name="search" :size="13" /> 搜索
        </button>
      </div>
      <div class="toolbar-right">
        <button
          class="btn btn-primary btn-sm"
          :disabled="rebuilding"
          title="选择知识库，对其已审核文档重新抽取实体/关系"
          @click="openRebuild"
        >
          <Icon name="refresh" :size="13" /> {{ rebuilding ? '重建中…' : '重建图谱' }}
        </button>
        <button class="btn btn-primary btn-sm" title="导出图谱" @click="toggleExportMenu">
          <Icon name="download" :size="13" /> 导出图谱 <Icon name="chevron-down" :size="12" />
        </button>
      </div>
    </div>

    <!-- ====== 主区：图布 + 右侧面板 ====== -->
    <div class="graph-body">
      <!-- 左：图布 -->
      <div class="canvas-area card">
        <!-- ====== 重建进度横幅（画布内顶部） ====== -->
        <div v-if="rebuildProgress" class="rebuild-banner" :class="`rb-${rebuildProgress.status}`">
          <span v-if="rebuildProgress.status === 'running'" class="rb-spinner" />
          <Icon v-else :name="rebuildProgress.status === 'done' ? 'check' : 'alert'" :size="16" class="rb-icon" />
          <span v-if="rebuildProgress.status === 'running'" class="rb-text">
            正在重建「{{ rebuildProgress.kbName }}」图谱… 已处理 {{ rebuildProgress.processed }}/{{ rebuildProgress.total }} 篇
          </span>
          <span v-else-if="rebuildProgress.status === 'done'" class="rb-text">「{{ rebuildProgress.kbName }}」图谱重建完成</span>
          <span v-else class="rb-text">「{{ rebuildProgress.kbName }}」图谱重建异常，请重试</span>
          <span
            v-if="rebuildProgress.status === 'running' && rebuildProgress.total"
            class="rb-track"
          ><i class="rb-fill" :style="{ width: Math.round(rebuildProgress.processed / rebuildProgress.total * 100) + '%' }" /></span>
        </div>

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
          :viewBox="`0 0 ${canvasW} ${canvasH}`"
          class="force-graph"
          preserveAspectRatio="xMidYMid meet"
          @pointerdown="onCanvasDown"
          @pointermove="onMove"
          @pointerup="onUp"
          @pointerleave="onUp"
          @wheel.prevent="onWheel"
          @dblclick="selectedId = null"
        >
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="2.5" orient="auto-start-reverse" markerUnits="strokeWidth">
              <path d="M0,0 L0,5 L7,2.5 z" fill="rgba(148,163,184,.7)" />
            </marker>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          <g ref="rootRef" :transform="`translate(${tx},${ty}) scale(${k})`">
            <!-- 边（曲线） -->
            <g class="edges" fill="none">
              <template v-for="(e, i) in (graph?.edges || [])" :key="'e' + i">
                <g v-if="edgeRender[i] && (!focusedNodeIds || (focusedNodeIds.has(e.source) && focusedNodeIds.has(e.target)))" :data-i="i" :class="{ dim: dimState.edges[i] }">
                  <path
                    :d="edgeRender[i]!.d"
                    :stroke="dimState.edges[i] ? 'rgba(100,116,139,.15)' : 'rgba(148,163,184,.38)'"
                    :stroke-width="focusId && (e.source === focusId || e.target === focusId) ? 2 : 1.2"
                    marker-end="url(#arrow)"
                  />
                  <text
                    v-if="edgeLabelShown(i, e)"
                    :x="edgeRender[i]!.lx"
                    :y="edgeRender[i]!.ly"
                    class="edge-label"
                    text-anchor="middle"
                  >{{ e.relation }}</text>
                </g>
              </template>
            </g>

            <!-- 节点 -->
            <g class="nodes">
              <g
                v-for="(n, i) in lNodes"
                v-show="!focusedNodeIds || focusedNodeIds.has(n.id)"
                :key="n.id"
                :transform="nodeRender[i].tf"
                :class="{ dim: dimState.nodes.get(n.id) }"
                class="gnode"
                @pointerenter="setHover(n.id)"
                @pointerleave="setHover(null)"
                @pointerdown="onNodeDown($event, n.id)"
                @click="selectedId = n.id"
                @dblclick.stop="focusNodeId === n.id ? exitFocus() : enterFocus(n.id)"
              >
                <!-- 聚焦发光环 -->
                <circle
                  v-if="focusNodeId === n.id"
                  :r="n.r + 7"
                  fill="none"
                  :stroke="nodeRender[i].fill"
                  stroke-width="2"
                  opacity=".6"
                  class="focus-glow"
                />
                <!-- 悬浮光晕 -->
                <circle
                  v-if="hoveredId === n.id && focusNodeId !== n.id"
                  :r="n.r + 4"
                  fill="none"
                  :stroke="nodeRender[i].fill"
                  stroke-width="1.5"
                  opacity=".35"
                />
                <circle
                  :r="n.r"
                  :fill="nodeRender[i].fill"
                  :opacity="selectedId === n.id ? 1 : 0.85"
                  :stroke="selectedId === n.id ? '#fff' : 'rgba(255,255,255,.25)'"
                  :stroke-width="selectedId === n.id ? 2.5 : 1"
                  :filter="selectedId === n.id ? 'url(#glow)' : undefined"
                />
                <text v-if="nodeLabelShown(n.id)" class="node-label" :y="n.r + 14" text-anchor="middle">{{ nodeRender[i].label }}</text>
              </g>
            </g>
          </g>
        </svg>

        <div v-if="graph && graph.nodes.length" class="canvas-footer">
          <div class="zoom-controls">
            <button class="zc-btn" title="缩小" @click="zoom(-1)"><Icon name="minus" :size="14" /></button>
            <span ref="zoomLabelRef" class="zoom-level">{{ Math.round(k * 100) }}%</span>
            <button class="zc-btn" title="放大" @click="zoom(1)"><Icon name="plus" :size="14" /></button>
            <button class="zc-btn" title="适配视图：缩放并平移到恰好容纳全图" @click="fitView"><Icon name="crosshair" :size="14" /></button>
          </div>
          <div class="legend">
            <span
              v-for="t in visibleLegendTypes"
              :key="t.label"
              class="leg-item leg-type"
              :class="{ active: legendHoverType === t.label }"
              @mouseenter="legendHoverType = t.label"
              @mouseleave="legendHoverType = null"
            >
              <i class="leg-dot" :style="{ background: typeColorMap[t.label] }"></i> {{ t.label }}
              <em class="leg-count">{{ t.count }}</em>
            </span>
            <button v-if="hiddenTypeCount" class="leg-more" @click="legendExpanded = !legendExpanded">
              {{ legendExpanded ? '收起' : `+${hiddenTypeCount} 更多` }}
            </button>
            <span v-if="presentKbs.length > 1" class="leg-divider"></span>
            <span v-if="presentKbs.length > 1" class="leg-item" v-for="b in presentKbs" :key="b.id">
              <i class="leg-dot" style="border-radius:2px" :style="{ background: kbColor[b.id] }"></i> {{ b.name }}
            </span>
          </div>
        </div>
        <p v-if="graph && graph.nodes.length" class="canvas-hint">拖拽节点可移动 · 滚轮缩放 · 双击节点进入聚焦模式 · 点击查看详情</p>

      </div>

      <!-- 右：数据面板 -->
      <aside class="stats-panel card">
        <div class="panel-head">
          <span class="panel-title">图谱数据统计</span>
        </div>

        <div class="stats-row">
          <div class="stat-card card" style="--card-accent: var(--accent-blue)">
            <div class="sc-icon"><Icon name="graph" :size="18"/></div>
            <div class="sc-body"><div class="sc-label">实体节点</div><div class="sc-value">{{ stats?.nodeCount ?? 0 }}</div></div>
          </div>
          <div class="stat-card card" style="--card-accent: var(--accent-green)">
            <div class="sc-icon"><Icon name="link" :size="18"/></div>
            <div class="sc-body"><div class="sc-label">关系边</div><div class="sc-value">{{ stats?.edgeCount ?? 0 }}</div></div>
          </div>
          <div class="stat-card card" style="--card-accent: var(--accent-amber)">
            <div class="sc-icon"><Icon name="tag" :size="18"/></div>
            <div class="sc-body"><div class="sc-label">实体类型</div><div class="sc-value">{{ Object.keys(stats?.typeCounts || {}).length }}</div></div>
          </div>
          <div class="stat-card card" style="--card-accent: var(--accent-blue)">
            <div class="sc-icon"><Icon name="link" :size="18"/></div>
            <div class="sc-body"><div class="sc-label">平均度数</div><div class="sc-value">{{ avgDegree }}</div></div>
          </div>
          <div class="stat-card card" style="--card-accent: var(--accent-green)">
            <div class="sc-icon"><Icon name="node" :size="18"/></div>
            <div class="sc-body"><div class="sc-label">最高度数</div><div class="sc-value">{{ maxDegree }}</div></div>
          </div>
          <div class="stat-card card" style="--card-accent: var(--accent-rose)">
            <div class="sc-icon"><Icon name="alert" :size="18"/></div>
            <div class="sc-body"><div class="sc-label">知识缺口</div><div class="sc-value">{{ gapSignals.length }}</div></div>
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
          <!-- 操作按钮 -->
          <div class="detail-actions">
            <button class="btn btn-outline btn-sm" @click="loadSource(selectedNode.id); sourceModalVisible = true">
              <Icon name="file" :size="12" /> 源文档
            </button>
            <button class="btn btn-sm" :class="focusNodeId === selectedNode.id ? 'btn-primary' : 'btn-outline'" @click="focusNodeId === selectedNode.id ? exitFocus() : enterFocus(selectedNode.id)">
              <Icon name="search" :size="12" /> 聚焦
            </button>
            <button class="btn btn-outline btn-sm" @click="$router.push({ path: '/chat', query: { q: `请解释 ${selectedNode.label} 及其相关概念`, kb: selectedNode.kbId } })">
              <Icon name="message" :size="12" /> 提问
            </button>
            <button class="btn btn-ghost btn-sm detail-btn-danger" @click="removeNode(selectedNode.id)">
              <Icon name="trash" :size="12" /> 删除
            </button>
          </div>
        </div>

    <!-- 源文档弹窗 -->
    <Teleport to="body">
      <div v-if="sourceModalVisible" class="source-modal-mask" @mousedown="sourceBd.onMouseDown" @mouseup="sourceBd.onMouseUp">
        <div class="source-modal-box">
          <div class="source-modal-head">
            <span class="source-modal-title">源文档</span>
            <button class="icon-btn" @click="sourceModalVisible = false"><Icon name="close" :size="14" /></button>
          </div>
          <div v-if="sourceLoading" class="source-modal-body source-modal-loading">加载中…</div>
          <div v-else-if="sourceInfo" class="source-modal-body">
            <div class="source-modal-doc">{{ sourceInfo.docTitle || '未知文档' }}</div>
            <pre class="source-modal-text">{{ sourceInfo.chunkContent || '无内容' }}</pre>
            <router-link v-if="sourceInfo.docId" :to="`/documents?kb=${sourceInfo.kbId}&doc=${sourceInfo.docId}`" class="source-modal-link" @click="sourceModalVisible = false">
              → 查看完整源文档
            </router-link>
          </div>
          <div class="source-modal-foot">
            <button class="btn btn-primary btn-sm" @click="sourceModalVisible = false">关闭</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 重建图谱弹窗 -->
    <Teleport to="body">
      <div v-if="rebuildVisible" class="source-modal-mask" @mousedown="rebuildBd.onMouseDown" @mouseup="rebuildBd.onMouseUp">
        <div class="source-modal-box" style="width: 360px">
          <div class="source-modal-head">
            <span class="source-modal-title">重建知识图谱</span>
            <button class="icon-btn" @click="rebuildVisible = false"><Icon name="close" :size="14" /></button>
          </div>
          <div class="source-modal-body">
            <p style="font-size:13px;color:var(--text-secondary);margin-bottom:14px">
              对选定知识库的全部已审核文档重新执行 LLM 实体/关系抽取，补全或重建图谱数据。
            </p>
            <label style="display:block;font-size:12px;font-weight:600;margin-bottom:6px;color:var(--text-secondary)">目标知识库</label>
            <CustomSelect v-model="rebuildKb" :options="kbRebuildOpts" placeholder="请选择知识库" width="100%" />
            <label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;margin-top:14px">
              <input v-model="rebuildClean" type="checkbox" style="accent-color:var(--brand)" />
              清空后全量重建（删除现有节点和关系再重抽）
            </label>
          </div>
          <div class="source-modal-foot" style="justify-content:flex-end;gap:8px">
            <button class="btn btn-ghost btn-sm" @click="rebuildVisible = false">取消</button>
            <button class="btn btn-primary btn-sm" :disabled="!rebuildKb" @click="confirmRebuild">开始重建</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 导出格式菜单：Teleport 到 body，避开画布卡片的 overflow:hidden 裁剪 -->
    <Teleport to="body">
      <template v-if="exportOpen">
        <div class="export-backdrop" @click="exportOpen = false" />
        <div class="export-menu" :style="{ top: `${exportMenuPos.top}px`, right: `${exportMenuPos.right}px` }">
          <button class="export-item" @click="doExport('png')"><Icon name="image" :size="14" /> PNG 图片</button>
          <button class="export-item" @click="doExport('csv-nodes')"><Icon name="table" :size="14" /> CSV · 实体表</button>
          <button class="export-item" @click="doExport('csv-edges')"><Icon name="link" :size="14" /> CSV · 关系表</button>
          <button class="export-item" @click="doExport('gexf')"><Icon name="graph" :size="14" /> GEXF（Gephi）</button>
          <button class="export-item" @click="doExport('json')"><Icon name="file-code" :size="14" /> JSON</button>
        </div>
      </template>
    </Teleport>


        <div class="section-block">
          <div class="section-title">实体类型分布</div>
          <div v-if="typeBars.length" class="type-bars">
            <div v-for="(t, i) in typeBars" :key="i" class="type-bar">
              <span class="tb-label">{{ t.label }}</span>
              <span class="tb-track"><i class="tb-fill" :style="{ width: t.pct + '%' }"></i></span>
              <span class="tb-count">{{ t.count }}</span>
            </div>
          </div>
          <div v-else class="graph-empty-state">
            <Icon name="archive" :size="22" />
            <span>暂无实体类型数据</span>
          </div>
        </div>

        <div class="section-block">
          <div class="section-title">热门知识点 Top 5</div>
          <div v-if="hotNodes.length" class="hot-list">
            <div v-for="(item, i) in hotNodes" :key="item.id" class="hot-item" @click="selectedId = item.id" @mouseenter="hoveredId = item.id" @mouseleave="hoveredId = null">
              <span class="hot-rank" :class="{ top3: i < 3 }">{{ i + 1 }}</span>
              <span class="hot-dot" :style="{ background: nodeColor(item.kbId) }"></span>
              <span class="hot-name">{{ item.label }}</span>
              <span class="hot-count">度数 <strong>{{ item.degree }}</strong></span>
            </div>
          </div>
          <div v-else class="graph-empty-state">
            <Icon name="archive" :size="22" />
            <span>暂无热门知识点</span>
          </div>
        </div>

        <div class="section-block">
          <div class="section-title">最近新增的实体</div>
          <div v-if="recentNodes.length" class="recent-list">
            <div v-for="n in recentNodes" :key="n.id" class="recent-item" @click="selectedId = n.id" @mouseenter="hoveredId = n.id" @mouseleave="hoveredId = null">
              <span class="recent-icon" :style="{ background: nodeColor(n.kbId) + '18', color: nodeColor(n.kbId) }">
                <Icon name="graph" :size="13" />
              </span>
              <span class="recent-name">{{ n.label }}</span>
              <span class="recent-time">{{ (n.createdAt || '').slice(5, 10) }}</span>
            </div>
          </div>
          <div v-else class="graph-empty-state">
            <Icon name="archive" :size="22" />
            <span>暂无新增实体</span>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>
