<script setup lang="ts">
// 首页大盘 — 数据总览（指标卡 + 文档分类占比 + 访问趋势 + 操作记录）。
import { computed, onMounted, ref, watch } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import Icon from '@/components/ui/Icon.vue'
import Pagination from '@/components/ui/Pagination.vue'
import DataTable from '@/components/ui/DataTable.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useToastStore } from '@/stores/toast'
import { getDashboardMetrics, getDocCategory, getTrend, getOperations, getDocumentById } from '@/api'
import { useTrendChart } from '@/composables/useTrendChart'
import '@/assets/dashboard.css'
import type {
  DashboardMetrics, TrendResponse, DocCategory,
  OperationsResponse, OperationLogItem, DocumentDetail,
} from '@/types/api'

const kb = useKnowledgeStore()
const toast = useToastStore()
const { chartW, chartH, makeTrend } = useTrendChart()

/* ---- 指标卡 ---- */
const metrics = ref<DashboardMetrics | null>(null)
async function loadMetrics() { metrics.value = await getDashboardMetrics() }
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

/* ---- 文档分类占比 ---- */
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

/* ---- 访问趋势（折线图）---- */
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

/* ---- 操作记录 ---- */
const opsData = ref<OperationsResponse | null>(null)
const opsPage = ref(1)
const opsPageSize = ref(10)
async function loadOps(page = opsPage.value, size = opsPageSize.value) {
  opsPage.value = page
  opsPageSize.value = size
  opsData.value = await getOperations(page, size)
}
const activityLog = computed<Array<{ time: string; user: string; type: string; content: string; file: string; action: string; docId: string | null }>>(() =>
  (opsData.value?.items ?? []).map((o: OperationLogItem) => ({
    time: fmtTime(o.createdAt),
    user: o.displayName || (o.userId ? `用户${o.userId.slice(0, 8)}` : '未知用户'),
    type: o.actionLabel,
    content: o.detail || defaultContent(o.action),
    file: o.detail && ['upload', 'approve', 'reject', 'delete'].includes(o.action) ? o.detail : '',
    action: o.action,
    docId: (o.relatedDocId && ['upload', 'approve', 'reject', 'delete'].includes(o.action)) ? o.relatedDocId : null,
  })),
)
const activityColumns = [
  { key: 'time', title: '操作时间', mono: true },
  { key: 'user', title: '操作用户' },
  { key: 'type', title: '操作类型' },
  { key: 'content', title: '操作内容', muted: true },
  { key: 'file', title: '相关文档' },
]
const ACT_ICONS: Record<string, string> = {
  login: 'user-circle', upload: 'upload', approve: 'check', reject: 'close',
  delete: 'trash', ask: 'sparkles', download: 'download',
}

/* ---- 文档预览 ---- */
const showPreview = ref(false)
const previewDoc = ref<DocumentDetail | null>(null)
const previewLoading = ref(false)
function handleDocPreview(row: { docId: string | null; file: string }) {
  if (row.docId) openPreview(row.docId)
}
async function openPreview(docId: string) {
  showPreview.value = false
  previewDoc.value = null
  previewLoading.value = true
  try {
    const result = await getDocumentById(docId)
    previewDoc.value = result
    showPreview.value = true
  } catch (e: any) {
    toast.error(`加载文档失败：${e?.message || e}`)
  } finally {
    previewLoading.value = false
  }
}
function closePreview() { showPreview.value = false; previewDoc.value = null }
function fmtTime(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
function defaultContent(action: string): string {
  return ({ login: '登录系统', upload: '上传了文档', approve: '审核通过文档', reject: '审核驳回文档', delete: '删除了文档', ask: '发起了一次 AI 问答', download: '下载了文档' } as Record<string, string>)[action] ?? '执行了操作'
}

onMounted(() => {
  if (!kb.loaded) kb.load()
  void loadMetrics(); void loadCategories(); void loadTrend(trendRange.value); void loadOps(1)
})
watch(trendRange, (r) => { void loadTrend(r) })
</script>

<template>
  <div class="dashboard">
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

      <div class="pie-panel card">
        <div class="panel-head">
          <span class="panel-title">文档分类占比</span>
          <Icon name="info" :size="13" class="phint" />
        </div>
        <div v-if="catTotal === 0" class="empty-hint">暂无文档</div>
        <div v-else class="cat-body">
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
            <span v-if="row.file" class="doc-link" @click.stop="handleDocPreview(row)">{{ row.file }}</span>
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

    <!-- 文档预览弹窗 -->
    <AppModal :show="showPreview" :title="previewDoc?.title || '文档预览'" wide @close="closePreview">
      <div v-if="previewLoading" class="modal-hint">加载中…</div>
      <template v-else-if="previewDoc">
        <div class="preview-meta">
          <span class="type-text">{{ previewDoc.type }}</span>
          <span class="col-time">{{ previewDoc.updatedAt?.slice(0, 16) || '' }}</span>
          <span class="status-badge mini" :class="'status-' + (previewDoc.status || '')">{{ previewDoc.status }}</span>
          <span v-if="previewDoc.originalFilename" class="doc-file-name">{{ previewDoc.originalFilename }}</span>
        </div>
        <pre class="preview-body">{{ previewDoc.contentMd || '（无内容）' }}</pre>
      </template>
    </AppModal>
  </div>
</template>
