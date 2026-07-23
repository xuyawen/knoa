<script setup lang="ts">
// 首页大盘 — 参考 640(2).png 原型：5 指标卡（带涨跌）+ 趋势折线图 + 分类饼图 + 操作记录
// P2 真实化：指标/趋势/饼图/操作记录/公告/文档统计/用户统计 全部来自后端接口，0 硬编码随机。
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useKnowledgeStore } from '@/stores/knowledge'
import Icon from '@/components/ui/Icon.vue'
import Pagination from '@/components/ui/Pagination.vue'
import DataTable from '@/components/ui/DataTable.vue'
import AppModal from '@/components/ui/AppModal.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import { useAuthStore } from '@/stores/auth'
import {
  getDashboardMetrics, getTrend, getDocCategory, getOperations, getAnnouncements, getDocStats, getUserStats,
  createAnnouncement, updateAnnouncement, deleteAnnouncement, getHotAsk, getKnowledgeGaps,
} from '@/api'
import type {
  DashboardMetrics, TrendResponse, DocCategory, DocStats, UserStats,
  OperationsResponse, OperationLogItem, Announcement, AnnouncementCreate, HotQueryItem,
} from '@/types/api'

const kb = useKnowledgeStore()
const { bases, health, trending } = storeToRefs(kb)
const auth = useAuthStore()
const props = defineProps<{ section?: string }>()
const section = computed(() => props.section ?? 'overview')

// 真实指标（知识库文档数合计，用于文档统计分区兜底）
const totalDocs = computed(() => bases.value.reduce((s, b) => s + b.documentCount, 0))

// ── 指标卡：真实 Dashboard 指标 ──
const metrics = ref<DashboardMetrics | null>(null)
async function loadMetrics() {
  metrics.value = await getDashboardMetrics()
}
const statCards = computed(() => {
  const m = metrics.value
  if (!m) return []
  const d = m.deltas
  return [
    { icon: 'doc', color: 'var(--accent-blue)', bg: 'var(--accent-blue-soft)', label: '文档总数', value: m.totalDocs.toLocaleString(), delta: pct(d.totalDocs), up: d.totalDocs >= 0 },
    { icon: 'plus', color: 'var(--accent-cyan)', bg: 'var(--accent-cyan-soft)', label: '今日新增文档', value: String(m.todayNewDocs), delta: pct(d.todayNewDocs), up: d.todayNewDocs >= 0 },
    { icon: 'sparkles', color: 'var(--accent-violet)', bg: 'var(--accent-violet-soft)', label: 'AI 问答次数', value: m.aiAnswers.toLocaleString(), delta: pct(d.aiAnswers), up: d.aiAnswers >= 0 },
    { icon: 'search', color: 'var(--accent-blue)', bg: 'var(--accent-blue-soft)', label: '用户搜索次数', value: m.userSearches.toLocaleString(), delta: pct(d.userSearches), up: d.userSearches >= 0 },
    { icon: 'users', color: 'var(--accent-violet)', bg: 'var(--accent-violet-soft)', label: '活跃用户数', value: String(m.activeUsers), delta: pct(d.activeUsers), up: d.activeUsers >= 0 },
  ]
})
function pct(v: number): string {
  const s = v > 0 ? '+' : ''
  return `${s}${v.toFixed(1)}%`
}

// ── 文档分类占比（真实，来自 getDocCategory）──
const categories = ref<DocCategory[]>([])
async function loadCategories() { categories.value = await getDocCategory() }
const catTotal = computed(() => categories.value.reduce((s, c) => s + c.count, 0) || 0)
const UNCAT = '未分类'
function isUncat(c: DocCategory) { return c.category === UNCAT || !c.category }
const uncatCount = computed(() => categories.value.filter(isUncat).reduce((s, c) => s + c.count, 0))
const classified = computed(() => categories.value.filter((c) => !isUncat(c)))
const classifiedTotal = computed(() => classified.value.reduce((s, c) => s + c.count, 0) || 0)
const classifiedCount = computed(() => classified.value.length)
const TOP_N = 8
function buildBar(label: string, value: number, seg: number) {
  const pctTotal = catTotal.value ? ((value / catTotal.value) * 100).toFixed(1) : '0'
  const width = classifiedTotal.value ? (value / classifiedTotal.value) * 100 : 0
  return { label, value, pctTotal, width, seg }
}
const barData = computed(() => {
  const sorted = [...classified.value].sort((a, b) => b.count - a.count)
  const rest = sorted.slice(TOP_N)
  const rows = sorted.slice(0, TOP_N).map((c, i) => buildBar(c.category, c.count, (i % 5) + 1))
  if (rest.length) rows.push(buildBar(`其他 (${rest.length})`, rest.reduce((s, c) => s + c.count, 0), 0))
  return rows
})

// ── 热门搜索榜（真实，来自 knowledge store / getTrending）──
const topTrending = computed(() => trending.value.slice(0, 8))

// ── 热门内容：热门问答榜 + 知识缺口榜（真实，来自 operation_log 聚合）──
const hotAsk = ref<HotQueryItem[]>([])
const knowledgeGaps = ref<HotQueryItem[]>([])
async function loadHotContent() {
  const [a, g] = await Promise.all([getHotAsk(), getKnowledgeGaps()])
  hotAsk.value = a
  knowledgeGaps.value = g
}

// ── 健康概览行（真实）──
const healthRows = computed(() =>
  health.value.map((h) => ({
    name: h.kb, docCount: h.docCount,
    reviewRate: Math.round(h.reviewRate * 100),
    retrievableRate: Math.round(h.retrievableRate * 100),
    healthScore: h.healthScore,
  })),
)

// ── 趋势折线图（真实，来自 getTrend；overview 与 访问分析 共用）──
type TrendRange = 'today' | 'week' | 'month'
const trendRange = ref<TrendRange>('today')
const trendData = ref<TrendResponse | null>(null)
async function loadTrend(range: TrendRange) { trendData.value = await getTrend(range) }
watch(trendRange, (r) => { void loadTrend(r) })
const activeTrend = computed(() => {
  const t = trendData.value
  if (!t) return { points: [] as number[], labels: [] as string[], max: 1, labelStep: 1 }
  // 访问趋势 = 问答 + 搜索 的总访问量
  const pts = t.points.map((p) => p.aiAnswers + p.searches)
  const labelStep = t.labels.length > 12 ? Math.ceil(t.labels.length / 8) : 1
  return { points: pts, labels: t.labels, max: Math.max(1, ...pts), labelStep }
})
// 明细表每列独立最大值，用于迷你条形图按比例缩放
const visitMaxAi = computed(() =>
  Math.max(1, ...(trendData.value?.points ?? []).map((p) => p.aiAnswers)),
)
const visitMaxSearch = computed(() =>
  Math.max(1, ...(trendData.value?.points ?? []).map((p) => p.searches)),
)
const chartH = 220
const chartW = 520
function buildPath(points: number[], max: number): string {
  if (!points.length) return ''
  const stepX = chartW / (points.length - 1 || 1)
  const padY = 20
  const drawH = chartH - padY * 2
  return points.map((v, i) => {
    const x = i * stepX
    const y = chartH - padY - (v / max) * drawH
    return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
  }).join(' ')
}
const linePath = computed(() => buildPath(activeTrend.value.points, activeTrend.value.max))
const areaPath = computed(() => {
  const p = linePath.value
  if (!p) return ''
  return `${p} L ${chartW.toFixed(1)} ${chartH} L 0 ${chartH} Z`
})
const dotCoords = computed(() =>
  activeTrend.value.points.map((v, i) => {
    const stepX = chartW / (activeTrend.value.points.length - 1 || 1)
    const padY = 20; const drawH = chartH - padY * 2
    return { cx: (i * stepX).toFixed(1), cy: (chartH - padY - (v / activeTrend.value.max) * drawH).toFixed(1), val: v }
  }),
)

// ── 操作记录（真实，来自 getOperations 分页）──
const opsData = ref<OperationsResponse | null>(null)
const opsPage = ref(1)
const opsPageSize = ref(10)
async function loadOps(page = opsPage.value, size = opsPageSize.value) {
  opsPage.value = page
  opsPageSize.value = size
  opsData.value = await getOperations(page, size)
}
const activityLog = computed<Array<{ time: string; user: string; type: string; content: string; file: string; action: string }>>(() =>
  (opsData.value?.items ?? []).map((o: OperationLogItem) => ({
    time: fmtTime(o.createdAt),
    user: o.displayName || (o.userId ? `用户${o.userId.slice(0, 8)}` : '未知用户'),
    type: o.actionLabel,
    content: o.detail || defaultContent(o.action),
    file: o.relatedDocId ? `…${o.relatedDocId.slice(-8)}` : '',
    action: o.action,
  })),
)
function fmtTime(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
function defaultContent(action: string): string {
  return ({ login: '登录系统', upload: '上传了文档', approve: '审核通过文档', reject: '审核驳回文档', delete: '删除了文档', ask: '发起了一次 AI 问答', download: '下载了文档' } as Record<string, string>)[action] ?? '执行了操作'
}
const ACT_ICONS: Record<string, string> = {
  login: 'user-circle', upload: 'upload', approve: 'check', reject: 'close',
  delete: 'trash', ask: 'sparkles', download: 'download',
}

// ── 列表列定义（交给通用 DataTable 渲染）──
const activityColumns = [
  { key: 'time', title: '操作时间', mono: true },
  { key: 'user', title: '操作用户' },
  { key: 'type', title: '操作类型' },
  { key: 'content', title: '操作内容', muted: true },
  { key: 'file', title: '相关文档' },
]
const statusDistColumns = [
  { key: 'status', title: '状态', strong: true },
  { key: 'count', title: '文档数' },
  { key: 'ratio', title: '占比' },
]
const healthColumns = [
  { key: 'name', title: '知识库', strong: true },
  { key: 'docCount', title: '文档数' },
  { key: 'reviewRate', title: '审核率' },
  { key: 'retrievableRate', title: '可检索率' },
  { key: 'healthScore', title: '健康分' },
]
const visitColumns = [
  { key: 'label', title: '时间', mono: true },
  { key: 'aiAnswers', title: '问答次数' },
  { key: 'searches', title: '搜索次数' },
]
const userStatusColumns = [
  { key: 'status', title: '状态' },
  { key: 'count', title: '用户数' },
  { key: 'ratio', title: '占比' },
]

// ── 文档统计分区（真实，来自 getDocCategory + doc-stats）──
const docStats = ref<DocStats | null>(null)
async function loadDocStats() { docStats.value = await getDocStats() }
const docStatsTotal = computed(() => docStats.value?.total ?? 0)
function byStatusCount(status: string): number {
  return docStats.value?.byStatus?.find((s) => s.status === status)?.count ?? 0
}

const STATUS_TAG_CLASS: Record<string, string> = {
  已审核: 'success',
  待复核: 'warning',
  已拒绝: 'danger',
}
function statusTagClass(s: string): string {
  return STATUS_TAG_CLASS[s] ?? 'muted'
}

// 文档统计：分类分布横向条形（TOP 8 + 其他）
const docStatsCatTotal = computed(() => docStats.value?.byCategory?.reduce((s, c) => s + c.count, 0) || 0)
function buildDocStatsBar(label: string, value: number, seg: number, total: number, max: number) {
  return {
    label,
    value,
    pct: total ? ((value / total) * 100).toFixed(1) : '0',
    width: max ? (value / max) * 100 : 0,
    seg,
  }
}
const docStatsBarData = computed(() => {
  const sorted = [...(docStats.value?.byCategory ?? [])].sort((a, b) => b.count - a.count)
  const max = Math.max(1, ...sorted.map((c) => c.count))
  const rest = sorted.slice(8)
  const rows = sorted.slice(0, 8).map((c, i) => buildDocStatsBar(c.category || '未分类', c.count, (i % 5) + 1, docStatsCatTotal.value, max))
  if (rest.length) rows.push(buildDocStatsBar(`其他 (${rest.length})`, rest.reduce((s, c) => s + c.count, 0), 0, docStatsCatTotal.value, max))
  return rows
})

// 文档统计：类型分布横向条形
const typeTotal = computed(() => docStats.value?.byType?.reduce((s, t) => s + t.count, 0) || 0)
const TYPE_ICON: Record<string, string> = {
  MD: 'file-text',
  TXT: 'file-text',
  DOCX: 'file-type',
  PDF: 'file',
}
const typeBarData = computed(() => {
  const sorted = [...(docStats.value?.byType ?? [])].sort((a, b) => b.count - a.count)
  const max = Math.max(1, ...sorted.map((t) => t.count))
  return sorted.map((t, i) => buildDocStatsBar(t.type, t.count, (i % 5) + 1, typeTotal.value, max))
})

// 文档统计：近7天新增趋势
const recentTrendMax = computed(() => Math.max(1, ...(docStats.value?.recentTrend ?? []).map((p) => p.count)))

// ── 系统公告（真实，来自 getAnnouncements）──
const announcements = ref<Announcement[]>([])
async function loadAnnouncements() { announcements.value = (await getAnnouncements()).items }

// 公告管理（仅 admin）
const showAnnModal = ref(false)
const editingAnn = ref<Announcement | null>(null)
const savingAnn = ref(false)
const deleteTarget = ref<Announcement | null>(null)
const annForm = ref({ title: '', content: '', level: 'info' as AnnouncementCreate['level'], pinned: false })
const LEVEL_OPTIONS: { value: NonNullable<AnnouncementCreate['level']>; label: string }[] = [
  { value: 'info', label: '普通' },
  { value: 'warning', label: '警告' },
  { value: 'success', label: '成功' },
  { value: 'error', label: '严重' },
]
function resetAnnForm() {
  annForm.value = { title: '', content: '', level: 'info', pinned: false }
  editingAnn.value = null
}
function openCreateAnn() {
  resetAnnForm()
  showAnnModal.value = true
}
function openEditAnn(a: Announcement) {
  editingAnn.value = a
  annForm.value = { title: a.title, content: a.content, level: a.level, pinned: a.pinned }
  showAnnModal.value = true
}
async function saveAnn() {
  const { title, content, level, pinned } = annForm.value
  if (!title.trim() || !content.trim()) return
  savingAnn.value = true
  try {
    if (editingAnn.value) {
      await updateAnnouncement(editingAnn.value.id, { title, content, level, pinned })
    } else {
      await createAnnouncement({ title, content, level, pinned })
    }
    showAnnModal.value = false
    await loadAnnouncements()
  } finally {
    savingAnn.value = false
  }
}
async function togglePin(a: Announcement) {
  await updateAnnouncement(a.id, { pinned: !a.pinned })
  await loadAnnouncements()
}
async function confirmDeleteAnn() {
  if (!deleteTarget.value) return
  await deleteAnnouncement(deleteTarget.value.id)
  deleteTarget.value = null
  await loadAnnouncements()
}

// ── 用户统计分区（真实，来自 /api/analytics/user-stats）──
const userStats = ref<UserStats | null>(null)
async function loadUserStats() { userStats.value = await getUserStats() }

const totalUsers = computed(() => userStats.value?.totalUsers ?? null)
const newUsers30 = computed(() => userStats.value?.newUsers30 ?? null)

const ROLE_LABEL: Record<string, string> = {
  admin: '管理员', editor: '编辑', viewer: '浏览者',
}
const ROLE_ICON: Record<string, string> = {
  admin: 'shield', editor: 'edit', viewer: 'eye',
}
const roleTotal = computed(() => userStats.value?.byRole?.reduce((s, r) => s + r.count, 0) || 0)
const roleBarData = computed(() => {
  const sorted = [...(userStats.value?.byRole ?? [])].sort((a, b) => b.count - a.count)
  const max = Math.max(1, ...sorted.map((r) => r.count))
  return sorted.map((r, i) => ({
    ...buildDocStatsBar(ROLE_LABEL[r.role] || r.role, r.count, (i % 5) + 1, roleTotal.value, max),
    key: r.role,
    icon: ROLE_ICON[r.role] || 'user',
  }))
})

function userStatusTagClass(s: string): string {
  return s === '启用' ? 'success' : 'danger'
}
const userStatusTotal = computed(() => userStats.value?.byStatus?.reduce((s, r) => s + r.count, 0) || 0)

// 用户活跃趋势折线（复用文档趋势的 SVG 尺寸与绘制函数）
const userActiveTrend = computed(() => {
  const pts = userStats.value?.activeTrend ?? []
  const counts = pts.map((p) => p.count)
  return { points: counts, labels: pts.map((p) => p.date), max: Math.max(1, ...counts, 0) }
})
const userLinePath = computed(() => buildPath(userActiveTrend.value.points, userActiveTrend.value.max))
const userAreaPath = computed(() => {
  const p = userLinePath.value
  if (!p) return ''
  return `${p} L ${chartW.toFixed(1)} ${chartH} L 0 ${chartH} Z`
})
const userDotCoords = computed(() =>
  userActiveTrend.value.points.map((v, i) => {
    const stepX = chartW / (userActiveTrend.value.points.length - 1 || 1)
    const padY = 20; const drawH = chartH - padY * 2
    return { cx: (i * stepX).toFixed(1), cy: (chartH - padY - (v / userActiveTrend.value.max) * drawH).toFixed(1), val: v }
  }),
)

// 近7天新增用户迷你柱状图
const recentNewMax = computed(() => Math.max(1, ...(userStats.value?.recentNew ?? []).map((p) => p.count)))

// ── 分区按需加载 ──
function loadSection(s: string) {
  if (s === 'overview') {
    void loadMetrics(); void loadCategories(); void loadTrend(trendRange.value); void loadOps(1)
  } else if (s === 'docs') {
    void loadDocStats()
  } else if (s === 'analytics') {
    void loadTrend(trendRange.value)
  } else if (s === 'announcements') {
    void loadAnnouncements()
  } else if (s === 'popular') {
    void loadHotContent()
  } else if (s === 'users') {
    void loadMetrics(); void loadUserStats()
  }
}
watch(section, (s) => loadSection(s), { immediate: true })

onMounted(() => {
  if (!kb.loaded) kb.load()
})
</script>

<template>
  <div class="dashboard">
    <!-- ====== overview ====== -->
    <template v-if="section === 'overview'">
      <!-- Row 1: 5 指标卡 -->
      <div class="stats-row">
        <div v-for="card in statCards" :key="card.label" class="stat-card card">
          <div class="sc-icon" :style="{ background: card.bg, color: card.color }">
            <Icon :name="card.icon" :size="22" />
          </div>
          <div class="sc-body">
            <div class="sc-label">{{ card.label }}</div>
            <div class="sc-value">{{ card.value }}</div>
            <div class="sc-delta" :class="{ up: card.up, down: !card.up }">
              较昨日 {{ card.delta }}
              <Icon :name="card.up ? 'arrow-up-right' : 'arrow-down-right'" :size="12" />
            </div>
          </div>
        </div>
      </div>

      <!-- Row 2: 图表区 -->
      <div class="charts-row">
        <!-- 左：访问趋势 -->
        <div class="chart-panel card">
          <div class="panel-head">
            <span class="panel-title">访问趋势</span>
            <Icon name="info" :size="13" class="phint" />
          </div>
          <div class="trend-tabs">
            <button v-for="r in [{k:'today',l:'今日'},{k:'week',l:'近7日'},{k:'month',l:'近30日'}]"
              :key="r.k" class="ttab"
              :class="{ active: trendRange === r.k }"
              @click="trendRange = r.k as TrendRange">{{ r.l }}</button>
          </div>
          <div class="chart-wrap">
            <svg :viewBox="`0 0 ${chartW} ${chartH}`" class="trend-svg" preserveAspectRatio="none">
              <defs>
                <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="var(--brand)" stop-opacity="0.18" />
                  <stop offset="100%" stop-color="var(--brand)" stop-opacity="0.01" />
                </linearGradient>
              </defs>
              <g class="grid-lines">
                <line v-for="n in 5" :key="n" :x1="0" :y1="(n-1)*(chartH/4)" :x2="chartW" :y2="(n-1)*(chartH/4)" stroke="var(--border)" stroke-dasharray="4,4" />
              </g>
              <path :d="areaPath" fill="url(#areaGrad)" />
              <path :d="linePath" fill="none" stroke="var(--brand)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
              <g v-for="(d, i) in dotCoords" :key="i">
                <circle :cx="d.cx" :cy="d.cy" r="3.5" fill="var(--bg-elevated, var(--bg-surface))" stroke="var(--brand)" stroke-width="1.8" />
                <title>{{ activeTrend.labels[i] }} · {{ d.val }}</title>
              </g>
            </svg>
            <div class="x-axis">
              <span v-for="(lbl, i) in activeTrend.labels" :key="i" class="x-lbl">
                <template v-if="i % activeTrend.labelStep === 0">{{ lbl }}</template>
              </span>
            </div>
          </div>
        </div>

        <!-- 右：文档分类占比 -->
        <div class="pie-panel card">
          <div class="panel-head">
            <span class="panel-title">文档分类占比</span>
            <Icon name="info" :size="13" class="phint" />
          </div>

          <div v-if="catTotal === 0" class="empty-hint">暂无文档</div>
          <div v-else class="cat-body">
            <!-- 分层：已分类 vs 未分类 -->
            <div class="cat-summary">
              <div class="cat-stack">
                <div
                  class="cat-stack-fill"
                  :style="{ width: (classifiedTotal && catTotal ? (classifiedTotal / catTotal) * 100 : 0) + '%' }"
                ></div>
              </div>
              <div class="cat-summary-meta">
                <span><span class="dot dot-ok"></span>已分类 {{ classifiedCount }} 类 · {{ classifiedTotal.toLocaleString() }} 条</span>
                <span><span class="dot dot-gray"></span>未分类 {{ uncatCount.toLocaleString() }} 条</span>
              </div>
            </div>

            <!-- 已分类分布：横向条形（降序，TOP 8 + 其他） -->
            <div class="cat-bars">
              <div v-for="b in barData" :key="b.label" class="cat-bar-row">
                <span class="cat-bar-label" :title="b.label">{{ b.label }}</span>
                <div class="cat-bar-track">
                  <div
                    class="cat-bar-fill"
                    :class="b.seg === 0 ? 'bar-uncat' : 'bar-seg-' + b.seg"
                    :style="{ width: (b.width || 0) + '%' }"
                  ></div>
                </div>
                <span class="cat-bar-val">{{ b.value.toLocaleString() }}</span>
                <span class="cat-bar-pct">{{ b.pctTotal }}%</span>
              </div>
              <div v-if="!barData.length" class="empty-hint">暂无已分类文档</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Row 3: 近期操作记录 -->
      <div class="ops-section card">
        <div class="panel-head">
          <span class="panel-title">近期操作记录</span>
        </div>
        <DataTable :columns="activityColumns" :rows="activityLog">
          <template #cell="{ row, col }">
            <template v-if="col.key === 'time'">{{ row.time }}</template>
            <template v-else-if="col.key === 'user'">{{ row.user }}</template>
            <template v-else-if="col.key === 'type'">
              <span class="act-tag">
                <Icon :name="ACT_ICONS[row.action] || 'file'" :size="12" />
                {{ row.type }}
              </span>
            </template>
            <template v-else-if="col.key === 'content'">{{ row.content }}</template>
            <template v-else-if="col.key === 'file'">
              <span v-if="row.file" class="doc-link">{{ row.file }}</span>
              <span v-else class="na">—</span>
            </template>
          </template>
          <template #empty>暂无操作记录</template>
        </DataTable>
        <Pagination
          v-if="(opsData?.total ?? 0) > 0"
          v-model:page="opsPage"
          v-model:page-size="opsPageSize"
          :total="opsData?.total ?? 0"
          :page-sizes="[10, 20, 50]"
          @update:page="loadOps()"
          @update:page-size="loadOps(1)"
        />
      </div>
    </template>

    <!-- ====== docs 分区 ====== -->
    <template v-else-if="section === 'docs'">
      <div class="stats-row">
        <div class="stat-card card"><div class="sc-icon" style="background:var(--accent-blue-soft);color:var(--accent-blue)"><Icon name="doc" :size="22"/></div><div class="sc-body"><div class="sc-label">文档总数</div><div class="sc-value">{{ (docStats?.total ?? totalDocs).toLocaleString() }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:var(--accent-green-soft);color:var(--accent-green)"><Icon name="check" :size="22"/></div><div class="sc-body"><div class="sc-label">已审核</div><div class="sc-value">{{ (byStatusCount('已审核')).toLocaleString() }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:var(--accent-amber-soft);color:var(--accent-amber)"><Icon name="alert" :size="22"/></div><div class="sc-body"><div class="sc-label">待复核</div><div class="sc-value">{{ byStatusCount('待复核') }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:var(--accent-violet-soft);color:var(--accent-violet)"><Icon name="folder" :size="22"/></div><div class="sc-body"><div class="sc-label">知识库数</div><div class="sc-value">{{ bases.length }}</div></div></div>
      </div>

      <div class="charts-row docs-row">
        <!-- 按状态分布 -->
        <div class="ops-section card">
          <div class="panel-head"><span class="panel-title">按状态分布</span></div>
          <DataTable :columns="statusDistColumns" :rows="docStats?.byStatus ?? []">
            <template #cell="{ row, col }">
              <template v-if="col.key === 'status'">
                <span class="status-tag" :class="statusTagClass(row.status)">{{ row.status }}</span>
              </template>
              <template v-else-if="col.key === 'count'">{{ row.count }}</template>
              <template v-else-if="col.key === 'ratio'">{{ docStatsTotal ? ((row.count / docStatsTotal) * 100).toFixed(1) + '%' : '—' }}</template>
            </template>
            <template #empty>暂无数据</template>
          </DataTable>
        </div>
        <!-- 按分类分布 -->
        <div class="ops-section card">
          <div class="panel-head"><span class="panel-title">按分类分布</span></div>
          <div class="cat-bars slim">
            <div v-for="b in docStatsBarData" :key="b.label" class="cat-bar-row">
              <span class="cat-bar-label" :title="b.label">{{ b.label }}</span>
              <div class="cat-bar-track"><div class="cat-bar-fill" :class="b.seg === 0 ? 'bar-uncat' : 'bar-seg-' + b.seg" :style="{ width: (b.width || 0) + '%' }"></div></div>
              <span class="cat-bar-val">{{ b.value.toLocaleString() }}</span>
              <span class="cat-bar-pct">{{ b.pct }}%</span>
            </div>
            <div v-if="!docStatsBarData.length" class="empty-hint">暂无数据</div>
          </div>
        </div>
      </div>

      <div class="charts-row docs-row">
        <!-- 按类型分布 -->
        <div class="ops-section card">
          <div class="panel-head"><span class="panel-title">按类型分布</span></div>
          <div class="cat-bars slim">
            <div v-for="b in typeBarData" :key="b.label" class="cat-bar-row">
              <span class="cat-bar-label type-label">
                <Icon :name="TYPE_ICON[b.label] || 'file'" :size="13" />
                {{ b.label }}
              </span>
              <div class="cat-bar-track"><div class="cat-bar-fill" :class="'bar-seg-' + b.seg" :style="{ width: (b.width || 0) + '%' }"></div></div>
              <span class="cat-bar-val">{{ b.value.toLocaleString() }}</span>
              <span class="cat-bar-pct">{{ b.pct }}%</span>
            </div>
            <div v-if="!typeBarData.length" class="empty-hint">暂无数据</div>
          </div>
        </div>
        <!-- 近7天新增文档 -->
        <div class="chart-panel card">
          <div class="panel-head"><span class="panel-title">近7天新增文档</span></div>
          <div v-if="(docStats?.recentTrend ?? []).length" class="mini-bars">
            <div v-for="p in docStats?.recentTrend" :key="p.date" class="mini-bar-col">
              <div class="mini-bar-track-v">
                <div class="mini-bar-fill-v" :style="{ height: (p.count / recentTrendMax) * 100 + '%' }"></div>
              </div>
              <span class="mini-bar-val">{{ p.count }}</span>
              <span class="mini-bar-date">{{ p.date }}</span>
            </div>
          </div>
          <div v-else class="empty-hint">暂无数据</div>
        </div>
      </div>

      <div class="ops-section card">
        <div class="panel-head"><span class="panel-title">各知识库文档分布</span></div>
        <DataTable :columns="healthColumns" :rows="healthRows">
          <template #cell="{ row, col }">
            <template v-if="col.key === 'name'">{{ row.name }}</template>
            <template v-else-if="col.key === 'docCount'">{{ row.docCount }}</template>
            <template v-else-if="col.key === 'reviewRate'">{{ row.reviewRate }}%</template>
            <template v-else-if="col.key === 'retrievableRate'">{{ row.retrievableRate }}%</template>
            <template v-else-if="col.key === 'healthScore'">
              <span class="score-pill" :class="row.healthScore >= 0.7 ? 'ok' : 'bad'">{{ Math.round(row.healthScore * 100) }}%</span>
            </template>
          </template>
          <template #empty>暂无数据</template>
        </DataTable>
      </div>
    </template>

    <!-- ====== popular 分区 ====== -->
    <template v-else-if="section === 'popular'">
      <div class="chart-panel card">
        <div class="panel-head"><span class="panel-title">热门搜索榜</span><Icon name="fire" :size="14" class="phint"/></div>
        <div v-if="topTrending.length" class="trend-list">
          <div v-for="(t,i) in topTrending" :key="t.question" class="trend-item">
            <span class="trend-rank" :class="'rk-'+Math.min(i+1,3)">{{ i+1 }}</span>
            <span class="trend-q">{{ t.question }}</span>
            <span class="trend-count">{{ t.count }}</span>
          </div>
        </div>
        <div v-else class="empty-hint">暂无热门搜索数据</div>
      </div>

      <div class="charts-row docs-row">
        <div class="chart-panel card">
          <div class="panel-head"><span class="panel-title">热门问答榜</span><Icon name="message" :size="14" class="phint"/></div>
          <div v-if="hotAsk.length" class="trend-list">
            <div v-for="(t,i) in hotAsk" :key="t.query" class="trend-item">
              <span class="trend-rank" :class="'rk-'+Math.min(i+1,3)">{{ i+1 }}</span>
              <span class="trend-q">{{ t.query }}</span>
              <span class="trend-count">{{ t.count }}</span>
            </div>
          </div>
          <div v-else class="empty-hint">近 30 天暂无问答记录</div>
        </div>

        <div class="chart-panel card">
          <div class="panel-head"><span class="panel-title">知识缺口榜</span><Icon name="alert" :size="14" class="phint"/></div>
          <div v-if="knowledgeGaps.length" class="trend-list">
            <div v-for="(t,i) in knowledgeGaps" :key="t.query" class="trend-item">
              <span class="trend-rank" :class="'rk-'+Math.min(i+1,3)">{{ i+1 }}</span>
              <span class="trend-q">{{ t.query }}</span>
              <span class="trend-count">{{ t.count }}</span>
            </div>
          </div>
          <div v-else class="empty-hint">近 30 天暂无知识缺口</div>
        </div>
      </div>
    </template>

    <!-- ====== 访问分析（真实：复用趋势图 + 访问量明细表）====== -->
    <template v-else-if="section === 'analytics'">
      <div class="chart-panel card">
        <div class="panel-head">
          <span class="panel-title">访问趋势</span>
          <Icon name="info" :size="13" class="phint" />
        </div>
        <div class="trend-tabs">
          <button v-for="r in [{k:'today',l:'今日'},{k:'week',l:'近7日'},{k:'month',l:'近30日'}]"
            :key="r.k" class="ttab"
            :class="{ active: trendRange === r.k }"
            @click="trendRange = r.k as TrendRange">{{ r.l }}</button>
        </div>
        <div class="chart-wrap">
          <svg :viewBox="`0 0 ${chartW} ${chartH}`" class="trend-svg" preserveAspectRatio="none">
            <defs>
              <linearGradient id="areaGrad2" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="var(--brand)" stop-opacity="0.18" />
                <stop offset="100%" stop-color="var(--brand)" stop-opacity="0.01" />
              </linearGradient>
            </defs>
            <g class="grid-lines">
              <line v-for="n in 5" :key="n" :x1="0" :y1="(n-1)*(chartH/4)" :x2="chartW" :y2="(n-1)*(chartH/4)" stroke="var(--border)" stroke-dasharray="4,4" />
            </g>
            <path :d="areaPath" fill="url(#areaGrad2)" />
            <path :d="linePath" fill="none" stroke="var(--brand)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
            <g v-for="(d, i) in dotCoords" :key="i">
              <circle :cx="d.cx" :cy="d.cy" r="3.5" fill="var(--bg-elevated, var(--bg-surface))" stroke="var(--brand)" stroke-width="1.8" />
              <title>{{ activeTrend.labels[i] }} · {{ d.val }}</title>
            </g>
          </svg>
          <div class="x-axis">
            <span v-for="(lbl, i) in activeTrend.labels" :key="i" class="x-lbl">
              <template v-if="i % activeTrend.labelStep === 0">{{ lbl }}</template>
            </span>
          </div>
        </div>
      </div>
      <div class="ops-section card">
        <div class="panel-head"><span class="panel-title">访问量明细</span></div>
        <DataTable :columns="visitColumns" :rows="trendData?.points ?? []">
          <template #cell="{ row, col, index }">
            <template v-if="col.key === 'label'">{{ trendData?.labels[index] }}</template>
            <template v-else-if="col.key === 'aiAnswers'">
              <div class="vcell">
                <div class="vbar vbar-ask" :style="{ width: (row.aiAnswers / visitMaxAi) * 100 + '%' }"></div>
                <span class="vnum">{{ row.aiAnswers }}</span>
              </div>
            </template>
            <template v-else-if="col.key === 'searches'">
              <div class="vcell">
                <div class="vbar vbar-search" :style="{ width: (row.searches / visitMaxSearch) * 100 + '%' }"></div>
                <span class="vnum">{{ row.searches }}</span>
              </div>
            </template>
          </template>
          <template #empty>暂无数据</template>
        </DataTable>
      </div>
    </template>

    <!-- ====== 用户统计（真实：来自 /api/analytics/user-stats）====== -->
    <template v-else-if="section === 'users'">
      <div class="stats-row three">
        <div class="stat-card card"><div class="sc-icon" style="background:var(--accent-violet-soft);color:var(--accent-violet)"><Icon name="users" :size="22"/></div><div class="sc-body"><div class="sc-label">活跃用户数（今日）</div><div class="sc-value">{{ userStats?.activeUsers ?? '—' }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:var(--accent-blue-soft);color:var(--accent-blue)"><Icon name="user-plus" :size="22"/></div><div class="sc-body"><div class="sc-label">总用户数</div><div class="sc-value">{{ totalUsers ?? '—' }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:var(--accent-green-soft);color:var(--accent-green)"><Icon name="sparkles" :size="22"/></div><div class="sc-body"><div class="sc-label">近30天新增</div><div class="sc-value">{{ newUsers30 ?? '—' }}</div></div></div>
      </div>

      <div class="charts-row docs-row">
        <!-- 按角色分布 -->
        <div class="ops-section card">
          <div class="panel-head"><span class="panel-title">按角色分布</span></div>
          <div class="cat-bars slim">
            <div v-for="b in roleBarData" :key="b.key" class="cat-bar-row">
              <span class="cat-bar-label type-label">
                <Icon :name="b.icon" :size="13" />
                {{ b.label }}
              </span>
              <div class="cat-bar-track"><div class="cat-bar-fill" :class="'bar-seg-' + b.seg" :style="{ width: (b.width || 0) + '%' }"></div></div>
              <span class="cat-bar-val">{{ b.value.toLocaleString() }}</span>
              <span class="cat-bar-pct">{{ b.pct }}%</span>
            </div>
            <div v-if="!roleBarData.length" class="empty-hint">{{ totalUsers === null ? '无权限查看' : '暂无数据' }}</div>
          </div>
        </div>
        <!-- 按状态分布 -->
        <div class="ops-section card">
          <div class="panel-head"><span class="panel-title">按状态分布</span></div>
          <DataTable :columns="userStatusColumns" :rows="userStats?.byStatus ?? []">
            <template #cell="{ row, col }">
              <template v-if="col.key === 'status'">
                <span class="status-tag" :class="userStatusTagClass(row.status)">{{ row.status }}</span>
              </template>
              <template v-else-if="col.key === 'count'">{{ row.count }}</template>
              <template v-else-if="col.key === 'ratio'">{{ userStatusTotal ? ((row.count / userStatusTotal) * 100).toFixed(1) + '%' : '—' }}</template>
            </template>
            <template #empty>{{ totalUsers === null ? '无权限查看' : '暂无数据' }}</template>
          </DataTable>
        </div>
      </div>

      <div class="charts-row docs-row">
        <!-- 近7天活跃用户趋势 -->
        <div class="chart-panel card">
          <div class="panel-head"><span class="panel-title">近7天活跃用户趋势</span></div>
          <div class="chart-wrap">
            <svg :viewBox="`0 0 ${chartW} ${chartH}`" class="trend-svg" preserveAspectRatio="none">
              <defs>
                <linearGradient id="areaGradUser" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="var(--accent-violet)" stop-opacity="0.18" />
                  <stop offset="100%" stop-color="var(--accent-violet)" stop-opacity="0.01" />
                </linearGradient>
              </defs>
              <g class="grid-lines">
                <line v-for="n in 5" :key="n" :x1="0" :y1="(n-1)*(chartH/4)" :x2="chartW" :y2="(n-1)*(chartH/4)" stroke="var(--border)" stroke-dasharray="4,4" />
              </g>
              <path :d="userAreaPath" fill="url(#areaGradUser)" />
              <path :d="userLinePath" fill="none" stroke="var(--accent-violet)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
              <g v-for="(d, i) in userDotCoords" :key="i">
                <circle :cx="d.cx" :cy="d.cy" r="3.5" fill="var(--bg-elevated, var(--bg-surface))" stroke="var(--accent-violet)" stroke-width="1.8" />
                <title>{{ userActiveTrend.labels[i] }} · {{ d.val }}</title>
              </g>
            </svg>
            <div class="x-axis">
              <span v-for="(lbl, i) in userActiveTrend.labels" :key="i" class="x-lbl">{{ lbl }}</span>
            </div>
          </div>
        </div>
        <!-- 近7天新增用户 -->
        <div class="chart-panel card">
          <div class="panel-head"><span class="panel-title">近7天新增用户</span></div>
          <div v-if="(userStats?.recentNew ?? []).length" class="mini-bars">
            <div v-for="p in userStats?.recentNew" :key="p.date" class="mini-bar-col">
              <div class="mini-bar-track-v"><div class="mini-bar-fill-v" :style="{ height: (p.count / recentNewMax) * 100 + '%' }"></div></div>
              <span class="mini-bar-val">{{ p.count }}</span>
              <span class="mini-bar-date">{{ p.date }}</span>
            </div>
          </div>
          <div v-else class="empty-hint">{{ totalUsers === null ? '无权限查看' : '暂无数据' }}</div>
        </div>
      </div>

    </template>

    <!-- ====== 系统公告（真实：getAnnouncements 列表 + admin 管理）====== -->
    <template v-else>
      <div v-if="auth.isAdmin" class="ann-toolbar">
        <button class="btn btn-primary btn-sm" @click="openCreateAnn">
          <Icon name="plus" :size="14" /> 新建公告
        </button>
      </div>
      <div v-if="announcements.length" class="ann-list">
        <div v-for="a in announcements" :key="a.id" class="ann-card card" :class="'lv-' + a.level">
          <div class="ann-head">
            <Icon :name="a.pinned ? 'pin' : 'bell'" :size="15" class="ann-ic" />
            <span class="ann-title">{{ a.title }}</span>
            <span v-if="a.pinned" class="ann-pin">置顶</span>
            <span class="ann-level" :class="'lvl-' + a.level">{{ { info: '普通', warning: '警告', success: '成功', error: '严重' }[a.level] }}</span>
            <span class="ann-time">{{ fmtTime(a.createdAt) }}</span>
            <template v-if="auth.isAdmin">
              <button class="ann-action" title="编辑" @click="openEditAnn(a)"><Icon name="edit" :size="14" /></button>
              <button class="ann-action" :title="a.pinned ? '取消置顶' : '置顶'" @click="togglePin(a)">
                <Icon :name="a.pinned ? 'pin-off' : 'pin'" :size="14" />
              </button>
              <button class="ann-action danger" title="删除" @click="deleteTarget = a"><Icon name="trash-2" :size="14" /></button>
            </template>
          </div>
          <div class="ann-content">{{ a.content }}</div>
        </div>
      </div>
      <div v-else class="empty-hint">暂无系统公告</div>

      <!-- 公告编辑弹框 -->
      <AppModal :show="showAnnModal" :title="editingAnn ? '编辑公告' : '新建公告'" wide @close="showAnnModal = false">
        <div class="ann-form">
          <div class="form-row">
            <label class="form-label">标题</label>
            <input v-model="annForm.title" class="form-input" placeholder="公告标题" maxlength="200" />
          </div>
          <div class="form-row">
            <label class="form-label">级别</label>
            <div class="seg">
              <button
                v-for="opt in LEVEL_OPTIONS"
                :key="opt.value"
                class="seg-btn"
                :class="{ active: annForm.level === opt.value }"
                @click="annForm.level = opt.value"
              >{{ opt.label }}</button>
            </div>
          </div>
          <div class="form-row">
            <label class="form-label">置顶</label>
            <label class="switch">
              <input type="checkbox" v-model="annForm.pinned" />
              <span class="switch-track"><span class="switch-knob" /></span>
              <span class="switch-text">{{ annForm.pinned ? '置顶' : '不置顶' }}</span>
            </label>
          </div>
          <div class="form-row align-start">
            <label class="form-label">内容</label>
            <textarea v-model="annForm.content" class="form-input ann-textarea" placeholder="公告内容" rows="6" />
          </div>
        </div>
        <template #foot>
          <button class="btn btn-ghost btn-sm" @click="showAnnModal = false">取消</button>
          <button
            class="btn btn-primary btn-sm"
            :disabled="savingAnn || !annForm.title.trim() || !annForm.content.trim()"
            @click="saveAnn"
          >{{ savingAnn ? '保存中…' : '保存' }}</button>
        </template>
      </AppModal>

      <ConfirmDialog
        :show="!!deleteTarget"
        title="删除公告"
        :message="deleteTarget ? `确认删除公告「${deleteTarget.title}」？该操作不可恢复。` : ''"
        confirm-text="删除"
        danger
        @close="deleteTarget = null"
        @confirm="confirmDeleteAnn"
      />
    </template>
  </div>
</template>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 20px; }

/* ---- 指标卡 ---- */
.stats-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }
.stats-row.three { grid-template-columns: repeat(3, 1fr); }
.stat-card {
  padding: 20px 22px;
  display: flex; align-items: center; gap: 16px;
}
.sc-icon {
  width: 50px; height: 50px; border-radius: 14px;
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.sc-body { display: flex; flex-direction: column; gap: 3px; }
.sc-label { font-size: 13px; color: var(--text-secondary); }
.sc-value {
  font-size: 26px; font-weight: 800; letter-spacing: -.02em;
  line-height: 1.15; color: var(--text-primary);
}
.sc-delta {
  display: inline-flex; align-items: center; gap: 2px;
  font-size: 12.5px; color: var(--text-tertiary);
}
/* 绿涨红跌（中文习惯，遵循开发计划约定） */
.sc-delta.up { color: var(--success); }
.sc-delta.down { color: var(--danger); }

/* ---- 图表行 ---- */
.charts-row { display: grid; grid-template-columns: calc((100% - 64px) * 3 / 5 + 32px) calc((100% - 64px) * 2 / 5 + 16px); gap: 16px; }
.charts-row.docs-row { grid-template-columns: 1fr 1fr; }
.panel-head { display: flex; align-items: center; gap: 6px; margin-bottom: 16px; }
.panel-title { font-size: 15px; font-weight: 700; color: var(--text-primary); }
.phint { color: var(--text-tertiary); cursor: pointer; }
.view-more {
  margin-left: auto; font-size: 12.5px; color: var(--brand);
  cursor: pointer; text-decoration: none;
}

/* ---- 趋势面板 ---- */
.chart-panel { padding: 22px 24px; overflow: hidden; }
.trend-tabs { display: flex; gap: 4px; margin-bottom: 16px; }
.ttab {
  padding: 5px 14px; border-radius: var(--radius-md);
  font-size: 12.5px; color: var(--text-secondary); background: transparent;
  cursor: pointer; border: none; font-family: inherit; transition: all var(--dur-fast);
}
.ttab:hover { background: var(--bg-hover); }
.ttab.active { background: var(--brand); color: var(--text-on-brand); font-weight: 600; }

.chart-wrap { position: relative; width: 100%; }
.trend-svg { width: 100%; height: auto; overflow: visible; }
.grid-lines line { stroke-opacity: .5; }

.x-axis {
  display: flex;
  margin-top: 8px; padding: 0 2px;
}
.x-lbl {
  flex: 1; text-align: center;
  font-size: 11px; color: var(--text-secondary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ---- 文档分类占比 ---- */
.pie-panel { padding: 22px 24px; }
.cat-body { display: flex; flex-direction: column; gap: 16px; }
.cat-summary { display: flex; flex-direction: column; gap: 8px; }
.cat-stack { height: 8px; border-radius: 4px; background: var(--bg-subtle); overflow: hidden; }
.cat-stack-fill { height: 100%; background: var(--brand); border-radius: 4px; transition: width .3s ease; }
.cat-summary-meta { display: flex; gap: 18px; flex-wrap: wrap; font-size: 12.5px; color: var(--text-secondary); }
.cat-summary-meta .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.cat-summary-meta .dot-ok { background: var(--success); }
.cat-summary-meta .dot-gray { background: var(--text-tertiary); }

.cat-bars { display: flex; flex-direction: column; gap: 10px; max-height: 280px; overflow-y: auto; padding-right: 4px; }
.cat-bar-row { display: grid; grid-template-columns: 120px 1fr 46px 48px; align-items: center; gap: 10px; }
.cat-bar-label { font-size: 12.5px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cat-bar-track { height: 8px; background: var(--bg-subtle); border-radius: 4px; overflow: hidden; }
.cat-bar-fill { height: 100%; border-radius: 4px; transition: width .3s ease; min-width: 2px; }
.cat-bar-val { font-size: 12.5px; font-weight: 600; color: var(--text-primary); text-align: right; }
.cat-bar-pct { font-size: 12px; color: var(--text-tertiary); text-align: right; }
.bar-seg-1 { background: var(--cat-1); }
.bar-seg-2 { background: var(--cat-2); }
.bar-seg-3 { background: var(--cat-3); }
.bar-seg-4 { background: var(--cat-4); }
.bar-seg-5 { background: var(--cat-5); }
.bar-uncat { background: var(--text-tertiary); }

/* 文档统计分区：紧凑条形 */
.cat-bars.slim { max-height: 220px; }
.cat-bar-row .type-label { display: inline-flex; align-items: center; gap: 5px; }

/* 状态 tag */
.status-tag {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 9px; border-radius: var(--radius-pill);
  font-size: 12px; font-weight: 500; line-height: 1.6;
}
.status-tag.success { background: var(--success-soft); color: var(--success); }
.status-tag.warning { background: var(--warning-soft); color: var(--warning); }
.status-tag.danger { background: var(--danger-soft); color: var(--danger); }
.status-tag.muted { background: var(--bg-subtle); color: var(--text-tertiary); }

/* 近7天新增文档迷你柱状图 */
.mini-bars {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 10px; height: 180px; padding: 8px 4px 0;
}
.mini-bar-col {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column; align-items: center; gap: 6px;
}
.mini-bar-track-v {
  width: 100%; height: 120px; background: var(--bg-subtle); border-radius: var(--radius-sm);
  display: flex; align-items: flex-end; overflow: hidden;
}
.mini-bar-fill-v {
  width: 100%; background: linear-gradient(180deg, var(--brand), color-mix(in srgb, var(--brand) 55%, transparent));
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  min-height: 2px; transition: height .3s ease;
}
.mini-bar-val { font-size: 12px; font-weight: 600; color: var(--text-primary); }
.mini-bar-date { font-size: 11px; color: var(--text-secondary); }

/* ---- 操作记录 ---- */
.ops-section { padding: 22px 24px; overflow: hidden; }

/* 访问量明细：迷你条形 + 数值 */
.vcell { display: flex; align-items: center; gap: 8px; min-width: 90px; }
.vbar { height: 8px; border-radius: 4px; flex-shrink: 0; transition: width var(--dur-fast) var(--ease-out); }
.vbar-ask { background: linear-gradient(90deg, color-mix(in srgb, var(--brand) 55%, transparent), var(--brand)); }
.vbar-search { background: linear-gradient(90deg, color-mix(in srgb, var(--accent-blue) 55%, transparent), var(--accent-blue)); }
.vnum { font-size: 13px; font-weight: 600; color: var(--text-primary); font-variant-numeric: tabular-nums; }

.act-tag {
  display:inline-flex; align-items:center; gap:4px; padding:2px 9px;
  border-radius:var(--radius-pill); font-size:12px; font-weight:500;
  background:var(--brand-soft); color:var(--brand);
}
.doc-link { color:var(--brand); font-size:12.5px; }
.na { color:var(--text-tertiary); }

/* ---- 热门搜索榜 ---- */
.trend-list { display:flex; flex-direction:column; gap:4px; }
.trend-item {
  display:flex; align-items:center; gap:12px; padding:9px 10px;
  border-radius:var(--radius-md); transition:background var(--dur-fast);
}
.trend-item:hover { background:var(--bg-hover); }
.trend-rank {
  width:22px; height:22px; flex-shrink:0; border-radius:6px;
  display:inline-flex; align-items:center; justify-content:center;
  font-size:12px; font-weight:700; background:var(--bg-surface); color:var(--text-secondary); border:1px solid var(--border);
}
.trend-rank.rk-1{background:var(--brand);color:var(--text-on-brand)}.trend-rank.rk-2{background:var(--brand-soft);color:var(--brand)}
.trend-rank.rk-3{background:var(--warning-soft);color:var(--warning)}
.trend-q { flex:1; font-size:13.5px; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.trend-count {
  flex-shrink:0; font-size:12px; font-weight:600; color:var(--brand);
  background:var(--brand-soft); padding:2px 9px; border-radius:var(--radius-pill);
}

/* ---- 公告管理 ---- */
.ann-toolbar { display:flex; justify-content:flex-end; }
.ann-list { display:flex; flex-direction:column; gap:12px; }
.ann-card { padding:16px 18px; border-left:3px solid var(--brand); }
.ann-card.lv-warning { border-left-color:var(--warning); }
.ann-card.lv-success { border-left-color:var(--success); }
.ann-card.lv-error { border-left-color:var(--danger); }
.ann-head { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.ann-ic { color:var(--brand); }
.ann-title { font-size:14.5px; font-weight:700; color:var(--text-primary); }
.ann-pin { font-size:11px; padding:1px 7px; border-radius:var(--radius-pill); background:var(--brand-soft); color:var(--brand); }
.ann-level { font-size:11px; padding:1px 7px; border-radius:var(--radius-pill); }
.ann-level.lvl-info { background:var(--bg-subtle); color:var(--text-secondary); }
.ann-level.lvl-warning { background:var(--warning-soft); color:var(--warning); }
.ann-level.lvl-success { background:var(--success-soft); color:var(--success); }
.ann-level.lvl-error { background:var(--danger-soft); color:var(--danger); }
.ann-time { margin-left:auto; font-size:12px; color:var(--text-tertiary); }
.ann-action {
  display:inline-flex; align-items:center; justify-content:center;
  width:26px; height:26px; border-radius:var(--radius-sm);
  color:var(--text-secondary); background:transparent; cursor:pointer;
  transition:all var(--dur-fast);
}
.ann-action:hover { background:var(--bg-hover); color:var(--text-primary); }
.ann-action.danger:hover { background:var(--danger-soft); color:var(--danger); }
.ann-content { font-size:13px; color:var(--text-secondary); line-height:1.6; white-space:pre-wrap; }
.ann-form { display:flex; flex-direction:column; gap:18px; }
.ann-form .form-row { display:flex; align-items:center; gap:14px; }
.ann-form .form-row.align-start { align-items:flex-start; }
.ann-form .form-label { width:56px; flex-shrink:0; font-size:13px; font-weight:500; color:var(--text-secondary); text-align:right; }
.ann-form .form-input {
  flex:1; min-width:0; height:var(--btn-h-md); padding:0 12px;
  background:var(--bg-surface); border:1px solid var(--border);
  border-radius:var(--radius-md); color:var(--text-primary); font-size:14px;
  transition:border-color var(--dur-fast), box-shadow var(--dur-fast);
}
.ann-form .form-input::placeholder { color:var(--text-placeholder); }
.ann-form .form-input:focus { outline:none; border-color:var(--brand); box-shadow:0 0 0 3px var(--brand-ring); }
.ann-textarea { min-height:140px; height:auto; padding:10px 12px; resize:vertical; line-height:1.6; }
.ann-form .seg { display:inline-flex; align-items:center; background:var(--bg-subtle); border:1px solid var(--border); border-radius:var(--radius-md); padding:3px; }
.ann-form .seg-btn {
  height:30px; padding:0 14px; border:none; border-radius:var(--radius-sm);
  background:transparent; color:var(--text-secondary); font-size:13px;
  cursor:pointer; transition:all var(--dur-fast);
}
.ann-form .seg-btn:hover { color:var(--text-primary); }
.ann-form .seg-btn.active { background:var(--brand); color:var(--text-on-brand); font-weight:600; box-shadow:var(--shadow-sm); }
.ann-form .switch { display:inline-flex; align-items:center; gap:10px; cursor:pointer; user-select:none; }
.ann-form .switch input { position:absolute; opacity:0; width:0; height:0; }
.ann-form .switch-track {
  position:relative; width:40px; height:22px; background:var(--bg-subtle);
  border:1px solid var(--border); border-radius:var(--radius-pill);
  transition:background var(--dur-fast), border-color var(--dur-fast);
}
.ann-form .switch-knob {
  position:absolute; top:2px; left:2px; width:16px; height:16px;
  background:var(--text-secondary); border-radius:50%;
  transition:transform var(--dur-fast), background var(--dur-fast);
}
.ann-form .switch input:checked + .switch-track { background:var(--brand); border-color:var(--brand); }
.ann-form .switch input:checked + .switch-track .switch-knob { transform:translateX(18px); background:#fff; }
.ann-form .switch-text { font-size:13px; color:var(--text-secondary); }
.ann-form .switch input:checked ~ .switch-text { color:var(--brand); font-weight:500; }

/* ---- 通用 ---- */
.score-pill {
  display:inline-block; min-width:30px; text-align:center; padding:2px 10px;
  border-radius:var(--radius-pill); font-weight:700; font-size:12px;
}
.score-pill.ok{color:var(--success);background:var(--success-soft)}
.score-pill.bad{color:var(--danger);background:var(--danger-soft)}
.empty-hint { padding:24px; text-align:center; color:var(--text-tertiary); font-size:13px; }

@media (max-width:1024px){
  .stats-row{grid-template-columns:repeat(3,1fr)}
  .charts-row{grid-template-columns:1fr}
}
@media (max-width:720px){ .stats-row{grid-template-columns:repeat(2,1fr)} }
</style>
