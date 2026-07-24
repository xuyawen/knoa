<script setup lang="ts">
// 首页大盘 — 文档统计（状态/分类/类型分布、近7天新增、各知识库分布）。
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useKnowledgeStore } from '@/stores/knowledge'
import Icon from '@/components/ui/Icon.vue'
import DataTable from '@/components/ui/DataTable.vue'
import { getDocStats } from '@/api'
import '@/assets/dashboard.css'
import type { DocStats } from '@/types/api'

const kb = useKnowledgeStore()
const { bases, health } = storeToRefs(kb)

const totalDocs = computed(() => bases.value.reduce((s, b) => s + b.documentCount, 0))

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

const healthRows = computed(() =>
  health.value.map((h) => ({
    name: h.kb, docCount: h.docCount,
    reviewRate: Math.round(h.reviewRate * 100),
    retrievableRate: Math.round(h.retrievableRate * 100),
    healthScore: h.healthScore,
  })),
)

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

const recentTrendMax = computed(() => Math.max(1, ...(docStats.value?.recentTrend ?? []).map((p) => p.count)))

onMounted(() => {
  if (!kb.loaded) kb.load()
  void loadDocStats()
})
</script>

<template>
  <div class="dashboard">
    <div class="stats-row">
      <div class="stat-card card"><div class="sc-icon" style="background:var(--accent-blue-soft);color:var(--accent-blue)"><Icon name="doc" :size="22"/></div><div class="sc-body"><div class="sc-label">文档总数</div><div class="sc-value">{{ (docStats?.total ?? totalDocs).toLocaleString() }}</div></div></div>
      <div class="stat-card card"><div class="sc-icon" style="background:var(--accent-green-soft);color:var(--accent-green)"><Icon name="check" :size="22"/></div><div class="sc-body"><div class="sc-label">已审核</div><div class="sc-value">{{ (byStatusCount('已审核')).toLocaleString() }}</div></div></div>
      <div class="stat-card card"><div class="sc-icon" style="background:var(--accent-amber-soft);color:var(--accent-amber)"><Icon name="alert" :size="22"/></div><div class="sc-body"><div class="sc-label">待复核</div><div class="sc-value">{{ byStatusCount('待复核') }}</div></div></div>
      <div class="stat-card card"><div class="sc-icon" style="background:var(--accent-violet-soft);color:var(--accent-violet)"><Icon name="folder" :size="22"/></div><div class="sc-body"><div class="sc-label">知识库数</div><div class="sc-value">{{ bases.length }}</div></div></div>
    </div>

    <div class="charts-row docs-row">
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
  </div>
</template>
