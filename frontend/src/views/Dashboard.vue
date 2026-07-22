<script setup lang="ts">
// 首页大盘 — 参考 640(2).png 原型：5 指标卡（带涨跌）+ 趋势折线图 + 分类饼图 + 操作记录
// P2 真实化：指标/趋势/饼图/操作记录/公告/文档统计/用户统计 全部来自后端接口，0 硬编码随机。
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useKnowledgeStore } from '@/stores/knowledge'
import Icon from '@/components/ui/Icon.vue'
import {
  getDashboardMetrics, getTrend, getDocCategory, getOperations, getAnnouncements, getUsers, getDocStats,
} from '@/api'
import type {
  DashboardMetrics, TrendResponse, DocCategory, DocStats,
  OperationsResponse, OperationLogItem, Announcement, UserOut,
} from '@/types/api'

const kb = useKnowledgeStore()
const { bases, health, trending } = storeToRefs(kb)
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
    { icon: 'doc', color: '#3b82f6', bg: 'rgba(59,130,246,0.10)', label: '文档总数', value: m.totalDocs.toLocaleString(), delta: pct(d.totalDocs), up: d.totalDocs >= 0 },
    { icon: 'plus', color: '#06b6d4', bg: 'rgba(6,182,212,0.10)', label: '今日新增文档', value: String(m.todayNewDocs), delta: pct(d.todayNewDocs), up: d.todayNewDocs >= 0 },
    { icon: 'sparkles', color: '#8b5cf6', bg: 'rgba(139,92,246,0.10)', label: 'AI 问答次数', value: m.aiAnswers.toLocaleString(), delta: pct(d.aiAnswers), up: d.aiAnswers >= 0 },
    { icon: 'search', color: '#3b82f6', bg: 'rgba(59,130,246,0.10)', label: '用户搜索次数', value: m.userSearches.toLocaleString(), delta: pct(d.userSearches), up: d.userSearches >= 0 },
    { icon: 'users', color: '#8b5cf6', bg: 'rgba(139,92,246,0.10)', label: '活跃用户数', value: String(m.activeUsers), delta: pct(d.activeUsers), up: d.activeUsers >= 0 },
  ]
})
function pct(v: number): string {
  const s = v > 0 ? '+' : ''
  return `${s}${v.toFixed(1)}%`
}

// ── 饼图：文档分类占比（真实，来自 getDocCategory）──
const CIRC = 2 * Math.PI * 46
const categories = ref<DocCategory[]>([])
async function loadCategories() { categories.value = await getDocCategory() }
const pieTotal = computed(() => categories.value.reduce((s, c) => s + c.count, 0) || 0)
const pieData = computed(() => {
  const total = pieTotal.value || 1
  let acc = 0
  return categories.value.map((c, i) => {
    const frac = c.count / total
    const len = frac * CIRC
    const dash = `${len.toFixed(1)} ${(CIRC - len).toFixed(1)}`
    const offset = (-acc * CIRC).toFixed(1)
    acc += frac
    return { label: c.category, value: c.count, pct: (frac * 100).toFixed(1), seg: (i % 5) + 1, dash, offset }
  })
})

// ── 热门搜索榜（真实，来自 knowledge store / getTrending）──
const topTrending = computed(() => trending.value.slice(0, 8))

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
  if (!t) return { points: [] as number[], labels: [] as string[], max: 1 }
  const pts = t.points.map((p) => p.aiAnswers)
  return { points: pts, labels: t.labels, max: Math.max(1, ...pts) }
})
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
async function loadOps(page = 1) {
  opsPage.value = page
  opsData.value = await getOperations(page, 20)
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

// ── 文档统计分区（真实，来自 getDocCategory + doc-stats）──
const docStats = ref<DocStats | null>(null)
async function loadDocStats() { docStats.value = await getDocStats() }
const docStatsTotal = computed(() => docStats.value?.total ?? 0)
function byStatusCount(status: string): number {
  return docStats.value?.byStatus?.find((s) => s.status === status)?.count ?? 0
}

// ── 系统公告（真实，来自 getAnnouncements）──
const announcements = ref<Announcement[]>([])
async function loadAnnouncements() { announcements.value = await getAnnouncements() }

// ── 用户统计分区（真实，来自 dashboard.activeUsers + /api/auth/users）──
const totalUsers = ref<number | null>(null)
const newUsers30 = ref<number | null>(null)
async function loadUsers() {
  // 活跃用户已在 metrics 中；总用户/近30天新增需 admin 接口，失败则降级只显示活跃数
  try {
    const users: UserOut[] = await getUsers()
    totalUsers.value = users.length
    const cutoff = Date.now() - 30 * 24 * 3600 * 1000
    newUsers30.value = users.filter((u) => {
      const t = u.createdAt ? new Date(u.createdAt).getTime() : NaN
      return !isNaN(t) && t >= cutoff
    }).length
  } catch {
    totalUsers.value = null
    newUsers30.value = null
  }
}

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
  } else if (s === 'users') {
    void loadMetrics(); void loadUsers()
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
            <div class="sc-delta" :class="{ up: card.up }">
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
              <span v-for="(lbl, i) in activeTrend.labels" :key="i" class="x-lbl">{{ lbl }}</span>
            </div>
          </div>
        </div>

        <!-- 右：文档分类占比 -->
        <div class="pie-panel card">
          <div class="panel-head">
            <span class="panel-title">文档分类占比</span>
            <Icon name="info" :size="13" class="phint" />
          </div>
          <div class="pie-body">
            <div class="donut-chart">
              <svg viewBox="0 0 120 120" class="donut-svg">
                <circle v-for="p in pieData" :key="p.label" cx="60" cy="60" r="46" fill="none"
                  stroke-width="18" :stroke-dasharray="p.dash" :stroke-dashoffset="p.offset"
                  class="donut-seg" :class="'seg-' + p.seg" transform="rotate(-90 60 60)" />
              </svg>
              <div class="donut-center">
                <div class="donut-total">{{ pieTotal.toLocaleString() }}</div>
                <div class="donut-label">文档总数</div>
              </div>
            </div>
            <div class="pie-legend">
              <div v-for="p in pieData" :key="p.label" class="legend-item">
                <span class="legend-dot" :class="'seg-' + p.seg"></span>
                <span class="legend-label">{{ p.label }}</span>
                <span class="legend-val">{{ p.value.toLocaleString() }}</span>
                <span class="legend-pct">{{ p.pct }}%</span>
              </div>
              <div v-if="!pieData.length" class="empty-hint">暂无文档</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Row 3: 近期操作记录 -->
      <div class="ops-section card">
        <div class="panel-head">
          <span class="panel-title">近期操作记录</span>
          <a href="#" class="view-more" @click.prevent="loadOps(opsPage + 1)">查看更多</a>
        </div>
        <table class="ops-table">
          <thead>
            <tr><th>操作时间</th><th>操作用户</th><th>操作类型</th><th>操作内容</th><th>相关文档</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in activityLog" :key="row.time + row.user + row.action">
              <td class="col-time">{{ row.time }}</td>
              <td>{{ row.user }}</td>
              <td>
                <span class="act-tag">
                  <Icon :name="ACT_ICONS[row.action] || 'file'" :size="12" />
                  {{ row.type }}
                </span>
              </td>
              <td class="col-content">{{ row.content }}</td>
              <td>
                <span v-if="row.file" class="doc-link">{{ row.file }}</span>
                <span v-else class="na">—</span>
              </td>
            </tr>
            <tr v-if="!activityLog.length"><td colspan="5" class="empty-hint">暂无操作记录</td></tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ====== docs 分区 ====== -->
    <template v-else-if="section === 'docs'">
      <h2 class="page-title">文档统计</h2>
      <div class="stats-row">
        <div class="stat-card card"><div class="sc-icon" style="background:rgba(59,130,246,.1);color:#3b82f6"><Icon name="doc" :size="22"/></div><div class="sc-body"><div class="sc-label">文档总数</div><div class="sc-value">{{ (docStats?.total ?? totalDocs).toLocaleString() }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:rgba(34,197,94,.1);color:#22c55e"><Icon name="check" :size="22"/></div><div class="sc-body"><div class="sc-label">已审核</div><div class="sc-value">{{ (byStatusCount('已审核')).toLocaleString() }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:rgba(245,158,11,.1);color:#f59e0b"><Icon name="alert" :size="22"/></div><div class="sc-body"><div class="sc-label">待复核</div><div class="sc-value">{{ byStatusCount('待复核') }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:rgba(139,92,246,.1);color:#8b5cf6"><Icon name="folder" :size="22"/></div><div class="sc-body"><div class="sc-label">知识库数</div><div class="sc-value">{{ bases.length }}</div></div></div>
      </div>

      <div class="charts-row">
        <!-- 按状态分布 -->
        <div class="ops-section card">
          <div class="panel-head"><span class="panel-title">按状态分布</span></div>
          <table class="ops-table">
            <thead><tr><th>状态</th><th>文档数</th><th>占比</th></tr></thead>
            <tbody>
              <tr v-for="row in docStats?.byStatus ?? []" :key="row.status">
                <td class="col-name">{{ row.status }}</td>
                <td>{{ row.count }}</td>
                <td>{{ docStatsTotal ? ((row.count / docStatsTotal) * 100).toFixed(1) + '%' : '—' }}</td>
              </tr>
              <tr v-if="!docStats?.byStatus?.length"><td colspan="3" class="empty-hint">暂无数据</td></tr>
            </tbody>
          </table>
        </div>
        <!-- 按分类分布 -->
        <div class="ops-section card">
          <div class="panel-head"><span class="panel-title">按分类分布</span></div>
          <table class="ops-table">
            <thead><tr><th>分类</th><th>文档数</th><th>占比</th></tr></thead>
            <tbody>
              <tr v-for="row in docStats?.byCategory ?? []" :key="row.category">
                <td class="col-name">{{ row.category }}</td>
                <td>{{ row.count }}</td>
                <td>{{ docStatsTotal ? ((row.count / docStatsTotal) * 100).toFixed(1) + '%' : '—' }}</td>
              </tr>
              <tr v-if="!docStats?.byCategory?.length"><td colspan="3" class="empty-hint">暂无数据</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="ops-section card">
        <div class="panel-head"><span class="panel-title">各知识库文档分布</span></div>
        <table class="ops-table">
          <thead><tr><th>知识库</th><th>文档数</th><th>审核率</th><th>可检索率</th><th>健康分</th></tr></thead>
          <tbody>
            <tr v-for="row in healthRows" :key="row.name">
              <td class="col-name">{{ row.name }}</td><td>{{ row.docCount }}</td><td>{{ row.reviewRate }}%</td><td>{{ row.retrievableRate }}%</td>
              <td><span class="score-pill" :class="row.healthScore >= 70 ? 'ok' : 'bad'">{{ row.healthScore }}</span></td>
            </tr>
            <tr v-if="!healthRows.length"><td colspan="5" class="empty-hint">暂无数据</td></tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ====== popular 分区 ====== -->
    <template v-else-if="section === 'popular'">
      <h2 class="page-title">热门内容</h2>
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
    </template>

    <!-- ====== 访问分析（真实：复用趋势图 + 访问量明细表）====== -->
    <template v-else-if="section === 'analytics'">
      <h2 class="page-title">访问分析</h2>
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
            <span v-for="(lbl, i) in activeTrend.labels" :key="i" class="x-lbl">{{ lbl }}</span>
          </div>
        </div>
      </div>
      <div class="ops-section card">
        <div class="panel-head"><span class="panel-title">访问量明细</span></div>
        <table class="ops-table">
          <thead><tr><th>时间</th><th>问答次数</th><th>搜索次数</th></tr></thead>
          <tbody>
            <tr v-for="(p, i) in (trendData?.points ?? [])" :key="i">
              <td class="col-time">{{ trendData?.labels[i] }}</td>
              <td>{{ p.aiAnswers }}</td>
              <td>{{ p.searches }}</td>
            </tr>
            <tr v-if="!(trendData?.points?.length)"><td colspan="3" class="empty-hint">暂无数据</td></tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ====== 用户统计（真实：活跃用户 + 总用户 + 近30天新增）====== -->
    <template v-else-if="section === 'users'">
      <h2 class="page-title">用户统计</h2>
      <div class="stats-row">
        <div class="stat-card card"><div class="sc-icon" style="background:rgba(139,92,246,.1);color:#8b5cf6"><Icon name="users" :size="22"/></div><div class="sc-body"><div class="sc-label">活跃用户数（今日）</div><div class="sc-value">{{ metrics?.activeUsers ?? '—' }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:rgba(59,130,246,.1);color:#3b82f6"><Icon name="user-plus" :size="22"/></div><div class="sc-body"><div class="sc-label">总用户数</div><div class="sc-value">{{ totalUsers ?? '—' }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:rgba(34,197,94,.1);color:#22c55e"><Icon name="sparkles" :size="22"/></div><div class="sc-body"><div class="sc-label">近30天新增</div><div class="sc-value">{{ newUsers30 ?? '—' }}</div></div></div>
      </div>
      <div class="ops-section card">
        <div class="panel-head"><span class="panel-title">说明</span></div>
        <p class="note-text">活跃用户数来自当日有操作（登录 / 问答 / 文档管理）的去重用户；总用户数与近30天新增来自用户列表（需管理员权限，无权限时仅显示活跃用户数）。</p>
      </div>
    </template>

    <!-- ====== 系统公告（真实：getAnnouncements 列表）====== -->
    <template v-else>
      <h2 class="page-title">系统公告</h2>
      <div v-if="announcements.length" class="ann-list">
        <div v-for="a in announcements" :key="a.id" class="ann-card card" :class="'lv-' + a.level">
          <div class="ann-head">
            <Icon :name="a.pinned ? 'pin' : 'bell'" :size="15" class="ann-ic" />
            <span class="ann-title">{{ a.title }}</span>
            <span v-if="a.pinned" class="ann-pin">置顶</span>
            <span class="ann-time">{{ fmtTime(a.createdAt) }}</span>
          </div>
          <div class="ann-content">{{ a.content }}</div>
        </div>
      </div>
      <div v-else class="empty-hint">暂无系统公告</div>
    </template>
  </div>
</template>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 20px; }

/* ---- 指标卡 ---- */
.stats-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }
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

/* ---- 图表行 ---- */
.charts-row { display: grid; grid-template-columns: 1.55fr 1fr; gap: 16px; }
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
.ttab.active { background: var(--brand); color: #fff; font-weight: 600; }

.chart-wrap { position: relative; width: 100%; }
.trend-svg { width: 100%; height: auto; overflow: visible; }
.grid-lines line { stroke-opacity: .5; }

.x-axis {
  display: flex; justify-content: space-between;
  margin-top: 8px; padding: 0 2px;
}
.x-lbl { font-size: 11px; color: var(--text-tertiary); white-space: nowrap; }

/* ---- 饼图 ---- */
.pie-panel { padding: 22px 24px; }
.pie-body { display: flex; align-items: center; gap: 24px; }
.donut-chart { position: relative; width: 130px; height: 130px; flex-shrink: 0; }
.donut-svg { width: 100%; height: 100%; }
.donut-seg.seg-1{stroke:var(--cat-1)}.donut-seg.seg-2{stroke:var(--cat-2)}
.donut-seg.seg-3{stroke:var(--cat-3)}.donut-seg.seg-4{stroke:var(--cat-4)}
.donut-seg.seg-5{stroke:var(--cat-5)}
.legend-dot.seg-1{background:var(--cat-1)}.legend-dot.seg-2{background:var(--cat-2)}
.legend-dot.seg-3{background:var(--cat-3)}.legend-dot.seg-4{background:var(--cat-4)}
.legend-dot.seg-5{background:var(--cat-5)}

.donut-center { position: absolute; top:50%; left:50%; transform:translate(-50%,-50%); text-align:center; }
.donut-total { font-size: 20px; font-weight: 800; color: var(--text-primary); }
.donut-label { font-size: 11px; color: var(--text-tertiary); }
.pie-legend { flex:1; display:flex; flex-direction:column; gap:10px; }
.legend-item { display:flex; align-items:center; gap:8px; font-size:13px; }
.legend-dot { width:10px; height:10px; border-radius:3px; flex-shrink:0; }
.legend-label { flex:1; color:var(--text-secondary); }
.legend-val { font-weight:600; color:var(--text-primary); min-width:48px; text-align:right; }
.legend-pct { color:var(--text-tertiary); min-width:44px; text-align:right; font-size:12px; }

/* ---- 操作记录 ---- */
.ops-section { padding: 22px 24px; overflow: hidden; }
.ops-table { width:100%; border-collapse:collapse; font-size:13px; }
.ops-table th {
  text-align:left; padding:10px 14px; background:var(--bg-subtle);
  color:var(--text-secondary); font-weight:600; font-size:12px;
  border-bottom:1px solid var(--border);
}
.ops-table td { padding:11px 14px; border-bottom:1px solid var(--border); color:var(--text-primary); }
.ops-table tr:last-child td { border-bottom:none; }
.col-time { font-family:monospace; font-size:12.5px; color:var(--text-tertiary); }
.col-content { color:var(--text-secondary); }
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
  font-size:12px; font-weight:700; background:var(--bg-subtle); color:var(--text-tertiary);
}
.trend-rank.rk-1{background:var(--brand);color:#fff}.trend-rank.rk-2{background:var(--brand-soft);color:var(--brand)}
.trend-rank.rk-3{background:var(--warning-soft);color:var(--warning)}
.trend-q { flex:1; font-size:13.5px; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.trend-count {
  flex-shrink:0; font-size:12px; font-weight:600; color:var(--brand);
  background:var(--brand-soft); padding:2px 9px; border-radius:var(--radius-pill);
}

/* ---- 公告卡片 ---- */
.ann-list { display:flex; flex-direction:column; gap:12px; }
.ann-card { padding:16px 18px; border-left:3px solid var(--brand); }
.ann-card.lv-warning { border-left-color:var(--warning); }
.ann-card.lv-success { border-left-color:var(--success); }
.ann-card.lv-error { border-left-color:var(--danger); }
.ann-head { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.ann-ic { color:var(--brand); }
.ann-title { font-size:14.5px; font-weight:700; color:var(--text-primary); }
.ann-pin { font-size:11px; padding:1px 7px; border-radius:var(--radius-pill); background:var(--brand-soft); color:var(--brand); }
.ann-time { margin-left:auto; font-size:12px; color:var(--text-tertiary); }
.ann-content { font-size:13px; color:var(--text-secondary); line-height:1.6; white-space:pre-wrap; }

/* ---- 通用 ---- */
.page-title { font-size:18px; font-weight:700; color:var(--text-primary); margin:0 0 16px; }
.col-name { font-weight:600; }
.score-pill {
  display:inline-block; min-width:30px; text-align:center; padding:2px 10px;
  border-radius:var(--radius-pill); font-weight:700; font-size:12px;
}
.score-pill.ok{color:var(--success);background:var(--success-soft)}
.score-pill.bad{color:var(--danger);background:var(--danger-soft)}
.empty-hint { padding:24px; text-align:center; color:var(--text-tertiary); font-size:13px; }
.note-text { font-size:13px; color:var(--text-secondary); line-height:1.7; margin:0; }

@media (max-width:1024px){
  .stats-row{grid-template-columns:repeat(3,1fr)}
  .charts-row{grid-template-columns:1fr}
}
@media (max-width:720px){ .stats-row{grid-template-columns:repeat(2,1fr)} }
</style>
