<script setup lang="ts">
// 首页大盘 — 用户统计（角色/状态分布、活跃趋势、近7天新增）。
import { computed, onMounted, ref, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import DataTable from '@/components/ui/DataTable.vue'
import { getUserStats, getTrend } from '@/api'
import { useTrendChart } from '@/composables/useTrendChart'
import '@/assets/dashboard.css'
import type { UserStats, TrendResponse } from '@/types/api'

const { chartW, chartH, makeTrend } = useTrendChart()

const userStats = ref<UserStats | null>(null)
async function loadUserStats() { userStats.value = await getUserStats() }

const totalUsers = computed(() => userStats.value?.totalUsers ?? null)
const newUsers30 = computed(() => userStats.value?.newUsers30 ?? null)

const roleTotal = computed(() => userStats.value?.byRole?.reduce((s, r) => s + r.count, 0) || 0)
const roleBarData = computed(() => {
  const sorted = [...(userStats.value?.byRole ?? [])].sort((a, b) => b.count - a.count)
  const max = Math.max(1, ...sorted.map((r) => r.count))
  return sorted.map((r, i) => ({
    label: (r as { name?: string }).name || r.role,
    value: r.count,
    width: (r.count / max) * 100,
    seg: (i % 5) + 1,
    key: r.role,
    pct: ((r.count / roleTotal.value) * 100).toFixed(1),
  }))
})

function userStatusTagClass(s: string): string {
  return s === '启用' ? 'success' : 'danger'
}
const userStatusColumns = [
  { key: 'status', title: '状态' },
  { key: 'count', title: '用户数' },
  { key: 'ratio', title: '占比' },
]
const userStatusTotal = computed(() => userStats.value?.byStatus?.reduce((s, r) => s + r.count, 0) || 0)

const userActiveTrend = computed(() => {
  const pts = userStats.value?.activeTrend ?? []
  const counts = pts.map((p) => p.count)
  return { points: counts, labels: pts.map((p) => p.date), max: Math.max(1, ...counts, 0) }
})
const userGeom = computed(() => makeTrend(userActiveTrend.value.points, userActiveTrend.value.max))
const userLinePath = computed(() => userGeom.value.linePath)
const userAreaPath = computed(() => userGeom.value.areaPath)
const userDotCoords = computed(() => userGeom.value.dotCoords)

const recentNewMax = computed(() => Math.max(1, ...(userStats.value?.recentNew ?? []).map((p) => p.count)))

type TrendRange = 'today' | 'week' | 'month'
const trendRange = ref<TrendRange>('today')
const trendData = ref<TrendResponse | null>(null)
async function loadTrend(range: TrendRange) { trendData.value = await getTrend(range) }

const askPoints = computed(() => (trendData.value?.points ?? []).map((p) => p.aiAnswers))
const searchPoints = computed(() => (trendData.value?.points ?? []).map((p) => p.searches))
const sharedMax = computed(() => Math.max(1, ...askPoints.value, ...searchPoints.value))
const askGeom = computed(() => makeTrend(askPoints.value, sharedMax.value))
const searchGeom = computed(() => makeTrend(searchPoints.value, sharedMax.value))
const labelStep = computed(() => {
  const n = trendData.value?.labels.length ?? 0
  return n > 12 ? Math.ceil(n / 8) : 1
})

onMounted(() => { void loadUserStats(); void loadTrend(trendRange.value) })
watch(trendRange, (r) => { void loadTrend(r) })
</script>

<template>
  <div class="dashboard">
    <div class="stats-row three">
      <div class="stat-card card" style="--card-accent: var(--accent-green)"><div class="sc-icon"><Icon name="users" :size="22"/></div><div class="sc-body"><div class="sc-label">活跃用户数（今日）</div><div class="sc-value">{{ userStats?.activeUsers ?? '—' }}</div></div></div>
      <div class="stat-card card" style="--card-accent: var(--accent-blue)"><div class="sc-icon"><Icon name="user-plus" :size="22"/></div><div class="sc-body"><div class="sc-label">总用户数</div><div class="sc-value">{{ totalUsers ?? '—' }}</div></div></div>
      <div class="stat-card card" style="--card-accent: var(--accent-violet)"><div class="sc-icon"><Icon name="sparkles" :size="22"/></div><div class="sc-body"><div class="sc-label">近30天新增</div><div class="sc-value">{{ newUsers30 ?? '—' }}</div></div></div>
    </div>

    <div class="charts-row docs-row">
      <div class="ops-section card">
        <div class="panel-head"><span class="panel-title">按角色分布</span></div>
        <div class="cat-bars slim">
          <div v-for="b in roleBarData" :key="b.key" class="cat-bar-row">
            <span class="cat-bar-label type-label">
              {{ b.label }}
            </span>
            <div class="cat-bar-track"><div class="cat-bar-fill" :class="'bar-seg-' + b.seg" :style="{ width: (b.width || 0) + '%' }"></div></div>
            <span class="cat-bar-val">{{ b.value.toLocaleString() }}</span>
            <span class="cat-bar-pct">{{ b.pct }}%</span>
          </div>
          <div v-if="!roleBarData.length" class="empty-hint">{{ totalUsers === null ? '无权限查看' : '暂无数据' }}</div>
        </div>
      </div>
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

    <div class="charts-row full-width">
      <div class="chart-panel card">
        <div class="panel-head">
          <span class="panel-title">访问趋势（问答 / 搜索）</span>
          <div class="trend-legend">
            <span class="lg-item"><i class="lg-dot ask"></i>问答</span>
            <span class="lg-item"><i class="lg-dot search"></i>搜索</span>
          </div>
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
              <linearGradient id="areaAskUsers" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="var(--accent-blue)" stop-opacity="0.16" />
                <stop offset="100%" stop-color="var(--accent-blue)" stop-opacity="0.01" />
              </linearGradient>
            </defs>
            <g class="grid-lines">
              <line v-for="n in 5" :key="n" :x1="0" :y1="(n-1)*(chartH/4)" :x2="chartW" :y2="(n-1)*(chartH/4)" stroke="var(--border)" stroke-dasharray="4,4" />
            </g>
            <path :d="askGeom.areaPath" fill="url(#areaAskUsers)" />
            <path :d="askGeom.linePath" fill="none" stroke="var(--accent-blue)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
            <path :d="searchGeom.linePath" fill="none" stroke="var(--accent-green)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
            <g v-for="(d, i) in askGeom.dotCoords" :key="'a'+i">
              <circle :cx="d.cx" :cy="d.cy" r="3.5" fill="var(--bg-elevated, var(--bg-surface))" stroke="var(--accent-blue)" stroke-width="1.8" />
              <title>{{ trendData?.labels[i] }} · 问答 {{ d.val }}</title>
            </g>
            <g v-for="(d, i) in searchGeom.dotCoords" :key="'s'+i">
              <circle :cx="d.cx" :cy="d.cy" r="3.5" fill="var(--bg-elevated, var(--bg-surface))" stroke="var(--accent-green)" stroke-width="1.8" />
              <title>{{ trendData?.labels[i] }} · 搜索 {{ d.val }}</title>
            </g>
          </svg>
          <div class="x-axis">
            <span v-for="(lbl, i) in (trendData?.labels ?? [])" :key="i" class="x-lbl">
              <template v-if="i % labelStep === 0">{{ lbl }}</template>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
