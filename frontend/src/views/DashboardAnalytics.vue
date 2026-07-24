<script setup lang="ts">
// 首页大盘 — 访问分析（访问趋势折线 + 访问量明细表）。
import { computed, onMounted, ref, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import DataTable from '@/components/ui/DataTable.vue'
import { getTrend } from '@/api'
import { useTrendChart } from '@/composables/useTrendChart'
import '@/assets/dashboard.css'
import type { TrendResponse } from '@/types/api'

const { chartW, chartH, makeTrend } = useTrendChart()

type TrendRange = 'today' | 'week' | 'month'
const trendRange = ref<TrendRange>('today')
const trendData = ref<TrendResponse | null>(null)
async function loadTrend(range: TrendRange) { trendData.value = await getTrend(range) }
const activeTrend = computed(() => {
  const t = trendData.value
  if (!t) return { points: [] as number[], labels: [] as string[], max: 1, labelStep: 1 }
  const pts = t.points.map((p) => p.aiAnswers + p.searches)
  const labelStep = t.labels.length > 12 ? Math.ceil(t.labels.length / 8) : 1
  return { points: pts, labels: t.labels, max: Math.max(1, ...pts), labelStep }
})
const trendGeom = computed(() => makeTrend(activeTrend.value.points, activeTrend.value.max))
const linePath = computed(() => trendGeom.value.linePath)
const areaPath = computed(() => trendGeom.value.areaPath)
const dotCoords = computed(() => trendGeom.value.dotCoords)

const visitColumns = [
  { key: 'label', title: '时间', mono: true },
  { key: 'aiAnswers', title: '问答次数' },
  { key: 'searches', title: '搜索次数' },
]
const visitMaxAi = computed(() =>
  Math.max(1, ...(trendData.value?.points ?? []).map((p) => p.aiAnswers)),
)
const visitMaxSearch = computed(() =>
  Math.max(1, ...(trendData.value?.points ?? []).map((p) => p.searches)),
)

onMounted(() => { void loadTrend(trendRange.value) })
watch(trendRange, (r) => { void loadTrend(r) })
</script>

<template>
  <div class="dashboard">
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
  </div>
</template>
