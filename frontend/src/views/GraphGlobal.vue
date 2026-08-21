<script setup lang="ts">
// 知识图谱 — 全局图谱视图（力导向图 + 右侧数据面板）。
// 数据/筛选/派生统计来自 useGraphData；力导向布局与画布拖拽/缩放仅在本视图。
import { ref, shallowRef, triggerRef, computed, watch, nextTick, onUnmounted } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import RefreshButton from '@/components/ui/RefreshButton.vue'
import { useGraphData, downloadBlob, dateStamp } from '@/composables/useGraphData'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { useBackdropClick } from '@/composables/useBackdropClick'
import '@/assets/graph.css'
import '@/assets/dashboard.css'
import type { GraphNode, GraphEdge } from '@/types/api'

const knowledge = useKnowledgeStore()
const auth = useAuthStore()
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
// 首屏落定标记：布局按真实尺寸算完并画完首帧前，遮罩盖住画布（见模板 canvas-settle-mask）
const settled = ref(false)
// 画布真实尺寸是否已实测（svg 挂载后由 svgRef watcher 置位）
let sizeKnown = false
const svgRef = ref<SVGSVGElement | null>(null)
const contentRef = ref<HTMLDivElement | null>(null)
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

// zoom 提交防抖（提前声明，供 fitView → cancelZoomCommit 在 immediate watch 中安全调用）
let pendingZoom: number | null = null
let zoomCommitTimer: ReturnType<typeof setTimeout> | null = null

function cancelZoomCommit() {
  if (zoomCommitTimer) { clearTimeout(zoomCommitTimer); zoomCommitTimer = null }
  pendingZoom = null
}

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
// （共享状态已有数据、watch 不会再触发）也能立即布局，避免画布空白。
// 尺寸未实测前（sizeKnown=false）不布局：svg 挂载量得真实尺寸后由 svgRef watcher 补布局，
// 避免先用默认 1100×680 布局、拿到真实尺寸后整图跳变（首屏“从下到上闪一下”的根因）
watch(graph, async (g) => {
  if (!g || !g.nodes.length) return
  settled.value = false
  if (!sizeKnown) return
  lNodes.value = computeLayout(g.nodes, g.edges)
  fitView()
  void loadGaps()
  await settleAfterPaint()
}, { immediate: true })

/** 揭帘：等布局提交后的首帧真正画完（双 rAF），再移除遮罩，遮住布局落位过程。
 * 后台标签页 rAF 会被节流甚至暂停，兜底超时保证遮罩必定移除 */
async function settleAfterPaint() {
  await nextTick()
  await new Promise<void>((resolve) => {
    let done = false
    const finish = () => { if (!done) { done = true; resolve() } }
    requestAnimationFrame(() => requestAnimationFrame(finish))
    setTimeout(finish, 300)
  })
  settled.value = true
}

// viewBox 动态跟随 svg 元素实际尺寸：canvas-area 高度由右侧面板撑开，
// 固定 viewBox（1100×680）在纵横比不符的容器里会被 meet 缩放成中间一条、上下留大片空边。
// viewBox 与元素同宽高比后，布局按屏幕实际形状填满，letterbox 空边彻底消失
let resizeRO: ResizeObserver | null = null
let resizeTimer: ReturnType<typeof setTimeout> | null = null
watch(svgRef, (el) => {
  resizeRO?.disconnect()
  resizeRO = null
  if (!el) { sizeKnown = false; return }
  // 挂载即同步实测真实尺寸（getBoundingClientRect 强制一次布局），随后再算首帧布局，
  // 避免先用默认 1100×680 出图、ResizeObserver 事后纠偏导致整图跳变
  const r0 = el.getBoundingClientRect()
  if (Math.round(r0.width) >= 100 && Math.round(r0.height) >= 100) {
    canvasW.value = Math.round(r0.width)
    canvasH.value = Math.round(r0.height)
  }
  sizeKnown = true
  // 尚未落定就补布局 + 揭帘：覆盖 graph watcher 因尺寸未定而搁置、
  // 以及 lNodes 残留旧布局但 settled 被复位（视口卸载重挂）两种情况
  const g = graph.value
  if (g && g.nodes.length && !settled.value) {
    lNodes.value = computeLayout(g.nodes, g.edges)
    fitView()
    void loadGaps()
    void settleAfterPaint()
  }
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

// 内容层挂载后应用初始视图变换：setup 阶段的 immediate watch([tx,ty,k]) 执行时 DOM 尚未挂载，
// writeViewTransform 拿不到元素，这里在内容层 div 出现后补写一次
watch(contentRef, (el) => {
  if (el) writeViewTransform()
})

// 进入页面 / 切换知识库时，若该库仍在后台重建（如刷新后），恢复进度横幅 + 轮询
watch(() => gFilterBiz.value || selectedKb.value, (kb) => {
  if (kb) void resumeRebuildIfRunning(kb)
}, { immediate: true })

/* ---- 高亮（悬浮 / 选中 / 搜索 / 图例透镜） ---- */
// 图例悬浮类型（透镜）：须在 dimState 之前定义——dimState 的 getter 引用了它，
// 而 watch(dimState) 注册时会立即求值一次，若此时它仍在 TDZ 会抛 ReferenceError
const legendHoverType = ref<string | null>(null)
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
// dim 直写 DOM：模板不再绑 :class dim（避免悬浮时全树 diff），
// 由此 watcher 在 DOM 更新后批量 toggle dim 类（O(n) 原生操作，绕过 Vue 重渲染）
watch(dimState, (ds) => {
  const svg = svgRef.value
  if (!svg) return
  // 节点 DOM 顺序与 lNodes 一致（v-show 不移除元素），按序对位即可
  const nodeEls = svg.querySelectorAll<SVGGElement>('g.nodes > g.gnode')
  const nodes = lNodes.value
  for (let i = 0; i < nodeEls.length; i++) {
    const id = nodes[i]?.id
    nodeEls[i].classList.toggle('dim', id ? !!ds.nodes.get(id) : false)
  }
  // 边可能被 v-show 隐藏（聚焦模式），用 data-i 定位而非位置索引
  const edgeEls = svg.querySelectorAll<SVGGElement>('g.edges > g[data-i]')
  for (const el of edgeEls) {
    el.classList.toggle('dim', !!ds.edges[Number(el.dataset.i)])
  }
}, { flush: 'post' })
// 边标签降噪：有焦点时只显示焦点相关边，无焦点时边少才全显
function edgeLabelShown(i: number, e: GraphEdge): boolean {
  if (dimState.value.edges[i]) return false
  const f = focusId.value
  if (f) return e.source === f || e.target === f
  return (graph.value?.edges.length || 0) <= 60
}
// 悬浮防抖：鼠标停留超过 300ms 才提交高亮，避免快速划过节点时高频 dim/undim 交替
// 导致“屏幕疯狂闪动”（每次提交都会重算 dimState 并批量 toggle 347 节点 + 406 边的 class）。
// 离开用 150ms 短缓冲：缓冲期内重入同一节点（鼠标抖动/相邻节点间隙）高亮原样保留，
// 避免“瞬间熄灭文重新点亮”；移到另一节点时立即清掉旧高亮，防止等待期间“陈旧高亮”残留
const HOVER_ENTER_DELAY = 300
const HOVER_LEAVE_DELAY = 150
let hoverEnterTimer: ReturnType<typeof setTimeout> | null = null
let hoverLeaveTimer: ReturnType<typeof setTimeout> | null = null
function setHover(id: string | null) {
  if (id !== null) {
    // pointerenter：取消待定的离开清除，重开 500ms 提交定时器
    if (hoverLeaveTimer) { clearTimeout(hoverLeaveTimer); hoverLeaveTimer = null }
    if (hoverEnterTimer) clearTimeout(hoverEnterTimer)
    if (hoveredId.value === id) return // 重入当前正高亮的节点：原样保留
    if (hoveredId.value !== null) hoveredId.value = null // 高亮着别的节点：立即清除避免陈旧高亮
    hoverEnterTimer = setTimeout(() => { hoverEnterTimer = null; hoveredId.value = id }, HOVER_ENTER_DELAY)
  } else {
    // pointerleave：取消未提交的进入定时器；已提交的高亮短缓冲后再清除
    if (hoverEnterTimer) { clearTimeout(hoverEnterTimer); hoverEnterTimer = null }
    if (hoveredId.value !== null && !hoverLeaveTimer) {
      hoverLeaveTimer = setTimeout(() => { hoverLeaveTimer = null; hoveredId.value = null }, HOVER_LEAVE_DELAY)
    }
  }
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
const LEGEND_COLLAPSED_COUNT = 10
const visibleLegendTypes = computed(() =>
  legendExpanded.value ? typeBars.value : typeBars.value.slice(0, LEGEND_COLLAPSED_COUNT)
)
const hiddenTypeCount = computed(() => Math.max(0, typeBars.value.length - LEGEND_COLLAPSED_COUNT))

/* ---- 交互：平移 / 拖拽 / 缩放 ----
 * 性能：原先每次 pointermove 都触发整棵 SVG（节点+边+标签，数百个元素）的全量 diff；
 * 现改为 rAF 合并 + 直接写 DOM——平移/缩放只更新视口 div 的 CSS transform（O(1)，GPU 合成），
 * 节点拖拽只更新该节点与相连边（O(度数)）；交互结束再提交回共享 ref，触发一次校准渲染。
 */
let panning = false
let dragging: string | null = null
let lastClient: { x: number; y: number } | null = null
// 交互期间的本地视图状态（watcher 与共享 tx/ty/k 同步，交互结束时提交回去）
let viewTx = 0
let viewTy = 0
let viewK = 1
let rafId = 0
let pendingPointer: { x: number; y: number } | null = null
// 节点拖拽：按下时一次性收集被拖节点 DOM 与相连边的元素，之后每帧只更新它们
let dragEl: SVGGElement | null = null
let dragPos: { x: number; y: number } | null = null
let dragEdgeEls: { path: SVGPathElement; label: SVGTextElement | null; e: GraphEdge }[] = []
// 节点拖拽按下时捕获的 屏幕→用户空间 逆矩阵（拖拽期间视图变换不变，矩阵稳定）
let dragInv: DOMMatrix | null = null

// 共享视图状态的外部变更（fitView / 缩放按钮）同步到本地镜像，并直写 DOM
// （模板 :transform 属性绑定会被 CSS transform 覆盖，仅作为初始/降级值）
watch([tx, ty, k], () => {
  viewTx = tx.value; viewTy = ty.value; viewK = k.value
  writeViewTransform()
}, { immediate: true })

onUnmounted(() => {
  if (rafId) cancelAnimationFrame(rafId)
  if (hoverEnterTimer) clearTimeout(hoverEnterTimer)
  if (hoverLeaveTimer) clearTimeout(hoverLeaveTimer)
  cancelZoomCommit()
  resizeRO?.disconnect()
  if (resizeTimer) clearTimeout(resizeTimer)
})

function writeViewTransform() {
  // 变换的是内层“内容层” div（canvas-content），而非接收指针事件的外层视口 div（canvas-viewport）：
  // CSS transform 会连同命中测试区域一起移动——若变换事件层本身，平移后其可交互区域随之挪走，
  // 原位置露出无法拖动的死区。故事件层固定铺满画布、内容层单独变换（d3-zoom/Leaflet 同款分层）。
  // 变换用 CSS transform 而非内层 <g> 属性：Chrome 不会给 <svg> 及内部 <g> 建独立合成层
  // （加 will-change 仍每帧重布局 + 重光栅全部元素，实测 ~45ms/帧），而 HTML div 可合成，
  // 提升后平移/缩放只需 GPU 重组（实测 ~5ms/帧）。viewBox 与元素实际尺寸一致（缩放=1），
  // translate(tx,ty) scale(k) 与原 <g> 属性 transform 数值等效
  const el = contentRef.value
  if (!el) return
  // 平移量取整到设备像素整数：高分屏（如 DPR=1.5）下分数平移会让合成层纹理每帧被
  // 分数偏移采样，细边线与文字的抗锯齿逐帧变化→视觉上“节点都在抖动”；取整后
  // 图像每帧整体移动整数个设备像素，采样模式恒定，抠图稳定不抖（viewTx 本身仍保留
  // 精确值用于增量计算与提交，只有显示值取整，误差不累积）
  const dpr = window.devicePixelRatio || 1
  const rx = Math.round(viewTx * dpr) / dpr
  const ry = Math.round(viewTy * dpr) / dpr
  el.style.transform = `translate(${rx}px, ${ry}px) scale(${viewK})`
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
    if (dragging && dragEl && dragPos && dragInv) {
      // dragInv 已含内容层 div 的 CSS transform，直接把屏幕坐标映射到节点坐标（无需再解 viewTx/viewK）
      const l = { x: p.x * dragInv.a + p.y * dragInv.b + dragInv.e, y: p.x * dragInv.c + p.y * dragInv.d + dragInv.f }
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
    } else if (panning && lastClient) {
      // 平移增量直接用 client 坐标差：内容层 div 的 translate 与屏幕像素 1:1（平移分量在 scale 之外），
      // 不经 getScreenCTM 反算——其结果含 div 自身 scale，逐帧重取会产生累积漂移（图谱“追不上”鼠标）
      viewTx += p.x - lastClient.x
      viewTy += p.y - lastClient.y
      lastClient = { x: p.x, y: p.y }
      writeViewTransform()
    }
  }
}
function onCanvasDown(e: PointerEvent) {
  if (dragging) return
  panning = true
  lastClient = { x: e.clientX, y: e.clientY }
  ;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
}
function onNodeDown(e: PointerEvent, id: string) {
  e.stopPropagation()
  dragging = id
  lastClient = null
  dragEl = e.currentTarget as SVGGElement
  // 拖拽起始捕获 屏幕→用户空间 逆矩阵：getScreenCTM 已含视口 div 的 CSS transform，
  // 其逆把屏幕坐标直接映射到节点坐标；拖拽期间视图变换不变，矩阵保持稳定
  dragInv = svgRef.value?.getScreenCTM()?.inverse() ?? null
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
  dragInv = null
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
      </div>
      <div class="toolbar-right">
        <RefreshButton :loading="loading" @click="() => fetchGraph()" />
        <button
          v-if="auth.hasPerm('kb_super')"
          class="btn btn-primary btn-sm"
          :disabled="rebuilding"
          title="选择知识库，对其已审核文档重新抽取实体/关系"
          @click="openRebuild"
        >
          <Icon name="sparkles" :size="13" /> {{ rebuilding ? '重建中…' : '重建图谱' }}
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

        <div
          v-else
          class="canvas-viewport"
          @pointerdown="onCanvasDown"
          @pointermove="onMove"
          @pointerup="onUp"
          @pointerleave="onUp"
          @wheel.prevent="onWheel"
          @dblclick="selectedId = null"
        >
        <div ref="contentRef" class="canvas-content">
        <svg
          ref="svgRef"
          :viewBox="`0 0 ${canvasW} ${canvasH}`"
          class="force-graph"
          preserveAspectRatio="xMidYMid meet"
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

          <g>
            <!-- 边（曲线） -->
            <g class="edges" fill="none">
              <g
                v-for="(e, i) in (graph?.edges || [])"
                v-show="edgeRender[i] && (!focusedNodeIds || (focusedNodeIds.has(e.source) && focusedNodeIds.has(e.target)))"
                v-memo="[edgeRender[i]?.d, edgeLabelShown(i, e), focusId === e.source || focusId === e.target, !focusedNodeIds || (focusedNodeIds.has(e.source) && focusedNodeIds.has(e.target)), e.relation]"
                :key="'e' + i"
                :data-i="i"
              >
                <path
                  :d="edgeRender[i]?.d || ''"
                  stroke="rgba(148,163,184,.38)"
                  :stroke-width="focusId && (e.source === focusId || e.target === focusId) ? 2 : 1.2"
                  marker-end="url(#arrow)"
                />
                <text
                  v-if="edgeLabelShown(i, e)"
                  :x="edgeRender[i]?.lx ?? 0"
                  :y="edgeRender[i]?.ly ?? 0"
                  class="edge-label"
                  text-anchor="middle"
                >{{ e.relation }}</text>
              </g>
            </g>

            <!-- 节点 -->
            <g class="nodes">
              <g
                v-for="(n, i) in lNodes"
                v-show="!focusedNodeIds || focusedNodeIds.has(n.id)"
                v-memo="[nodeRender[i].tf, nodeRender[i].fill, nodeRender[i].label, hoveredId === n.id, selectedId === n.id, focusNodeId === n.id, nodeLabelShown(n.id), !focusedNodeIds || focusedNodeIds.has(n.id)]"
                :key="n.id"
                :transform="nodeRender[i].tf"
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
        </div>
        </div>

        <!-- 首帧落定遮罩：布局按实测尺寸算完、首帧画完后才揭帘（settled），
             遮住视口挂载/布局归位过程，消除首屏“从下到上闪一下”。
             仅在确有数据待落定时显示：空图谱/加载失败走各自的空态与错误路径，
             否则 settled 永不置真、遮罩会盖死画布 -->
        <div v-if="!settled && !loading && graph && graph.nodes.length" class="canvas-state canvas-settle-mask">
          <div class="dot-row"><span class="dot" /><span class="dot" /><span class="dot" /></div>
          <p>正在构建知识图谱…</p>
        </div>

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
          <EmptyState v-else />
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
          <EmptyState v-else />
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
          <EmptyState v-else />
        </div>
      </aside>
    </div>
  </div>
</template>
