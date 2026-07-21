<script setup lang="ts">
// 首页大盘 — 1:1 还原截图布局（5 指标卡 + 图表行 + 表格）。
// 后端无访问趋势/问答次数等分析接口，故「尽力映射」真实数据：
//   · 指标卡：知识库数 / 文档总数 / 待复核 / 平均健康分 / 热门问题
//   · 左面板：热门搜索榜（/api/trending）
//   · 右面板：知识库文档分布（/api/knowledge-bases）
//   · 底部表：知识库健康概览（health）
// 所有颜色均走 style.css 的 CSS 变量（含暗色覆盖），不写死 hex。
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useKnowledgeStore } from '@/stores/knowledge'
import Icon from '@/components/ui/Icon.vue'
import ComingSoon from '@/components/ui/ComingSoon.vue'

const kb = useKnowledgeStore()
const { bases, health, trending } = storeToRefs(kb)

const props = defineProps<{ section?: string }>()
const section = computed(() => props.section ?? 'overview')

onMounted(() => {
  if (!kb.loaded) kb.load()
})

// ── 真实指标 ──
const totalDocs = computed(() => bases.value.reduce((s, b) => s + b.documentCount, 0))
const pendingDocs = computed(() => bases.value.reduce((s, b) => s + b.pendingCount, 0))
const avgHealth = computed(() => {
  if (!health.value.length) return 0
  return Math.round(health.value.reduce((s, h) => s + h.healthScore, 0) / health.value.length)
})
const lowHealth = computed(() => health.value.filter((h) => h.healthScore < 70).length)

const stats = computed(() => [
  { icon: 'folder', tone: 'blue', label: '知识库数', value: String(bases.value.length), delta: '', up: true },
  { icon: 'doc', tone: 'cyan', label: '文档总数', value: totalDocs.value.toLocaleString(), delta: '', up: true },
  { icon: 'warning', tone: 'orange', label: '待复核文档', value: String(pendingDocs.value), delta: '', up: pendingDocs.value === 0 },
  { icon: 'heart', tone: 'green', label: '平均健康分', value: String(avgHealth.value), delta: '', up: avgHealth.value >= 70 },
  { icon: 'search', tone: 'purple', label: '热门问题', value: String(trending.value.length), delta: '', up: true },
])

// ── 饼图：知识库文档分布（真实）──
const pieTotal = computed(() => totalDocs.value)
const CIRC = 2 * Math.PI * 46 // 环形周长 ≈ 289
const pieData = computed(() => {
  const total = pieTotal.value || 1
  let acc = 0
  const palette = [1, 2, 3, 4, 5]
  return bases.value.map((b, i) => {
    const v = b.documentCount
    const frac = v / total
    const len = frac * CIRC
    const dash = `${len.toFixed(1)} ${(CIRC - len).toFixed(1)}`
    const offset = (-acc * CIRC).toFixed(1)
    acc += frac
    return { label: b.name, value: v, pct: (frac * 100).toFixed(1) + '%', seg: palette[i % 5], dash, offset }
  })
})

// ── 热门搜索榜（真实）──
const topTrending = computed(() => trending.value.slice(0, 8))

// ── 健康概览表（真实）──
const healthRows = computed(() =>
  health.value.map((h) => ({
    name: h.kb,
    docCount: h.docCount,
    reviewRate: Math.round(h.reviewRate * 100),
    retrievableRate: Math.round(h.retrievableRate * 100),
    healthScore: h.healthScore,
  })),
)
</script>

<template>
  <div class="dashboard">
    <!-- ====== 首页大盘：数据总览 ====== -->
    <template v-if="section === 'overview'">
    <!-- ====== Row 1: 指标卡 ====== -->
    <div class="stats-row">
      <div v-for="s in stats" :key="s.label" class="stat-card card" :class="'tone-' + s.tone">
        <div class="stat-icon-wrap">
          <Icon :name="s.icon" :size="22" />
        </div>
        <div class="stat-info">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-delta" :class="{ up: s.up }">
            <template v-if="s.delta">{{ s.delta }}</template>
            <template v-else>实时</template>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== Row 2: 图表区（左右分栏）====== -->
    <div class="charts-row">
      <!-- 左：热门搜索榜 -->
      <div class="chart-panel card">
        <div class="panel-head">
          <span class="panel-title">热门搜索</span>
          <Icon name="fire" :size="14" class="info-hint" />
        </div>
        <div v-if="topTrending.length" class="trend-list">
          <div v-for="(t, i) in topTrending" :key="t.question" class="trend-item">
            <span class="trend-rank" :class="'rk-' + Math.min(i + 1, 3)">{{ i + 1 }}</span>
            <span class="trend-q">{{ t.question }}</span>
            <span class="trend-count">{{ t.count }}</span>
          </div>
        </div>
        <div v-else class="empty-hint">暂无热门搜索数据</div>
      </div>

      <!-- 右：知识库文档分布 -->
      <div class="pie-panel card">
        <div class="panel-head">
          <span class="panel-title">知识库文档分布</span>
          <Icon name="alert" :size="14" class="info-hint" />
        </div>
        <div class="pie-body">
          <div class="donut-chart">
            <svg viewBox="0 0 120 120" class="donut-svg">
              <circle
                v-for="p in pieData"
                :key="p.label"
                cx="60" cy="60" r="46" fill="none"
                stroke-width="18"
                :stroke-dasharray="p.dash"
                :stroke-dashoffset="p.offset"
                class="donut-seg"
                :class="'seg-' + p.seg"
                transform="rotate(-90 60 60)"
              />
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
              <span class="legend-value">{{ p.value.toLocaleString() }}</span>
              <span class="legend-pct">{{ p.pct }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== Row 3: 知识库健康概览 ====== -->
    <div class="ops-section card">
      <div class="panel-head">
        <span class="panel-title">知识库健康概览</span>
        <span v-if="lowHealth" class="warn-flag">⚠ {{ lowHealth }} 个库健康分偏低</span>
      </div>
      <table class="ops-table">
        <thead>
          <tr>
            <th>知识库</th><th>文档数</th><th>审核率</th><th>可检索率</th><th>健康分</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in healthRows" :key="row.name">
            <td class="col-name">{{ row.name }}</td>
            <td>{{ row.docCount }}</td>
            <td>{{ row.reviewRate }}%</td>
            <td>{{ row.retrievableRate }}%</td>
            <td>
              <span class="score-pill" :class="row.healthScore >= 70 ? 'ok' : 'bad'">{{ row.healthScore }}</span>
            </td>
          </tr>
          <tr v-if="!healthRows.length">
            <td colspan="5" class="empty-hint">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </div>
    </template>

    <!-- ====== 首页大盘：文档统计 ====== -->
    <template v-else-if="section === 'docs'">
      <h2 class="page-title">文档统计</h2>
      <div class="stats-row">
        <div class="stat-card card tone-blue">
          <div class="stat-icon-wrap"><Icon name="doc" :size="22" /></div>
          <div class="stat-info"><div class="stat-label">文档总数</div><div class="stat-value">{{ totalDocs.toLocaleString() }}</div></div>
        </div>
        <div class="stat-card card tone-green">
          <div class="stat-icon-wrap"><Icon name="check" :size="22" /></div>
          <div class="stat-info"><div class="stat-label">已审核</div><div class="stat-value">{{ (totalDocs - pendingDocs).toLocaleString() }}</div></div>
        </div>
        <div class="stat-card card tone-orange">
          <div class="stat-icon-wrap"><Icon name="alert" :size="22" /></div>
          <div class="stat-info"><div class="stat-label">待复核</div><div class="stat-value">{{ pendingDocs }}</div></div>
        </div>
        <div class="stat-card card tone-purple">
          <div class="stat-icon-wrap"><Icon name="folder" :size="22" /></div>
          <div class="stat-info"><div class="stat-label">知识库数</div><div class="stat-value">{{ bases.length }}</div></div>
        </div>
      </div>
      <div class="ops-section card">
        <div class="panel-head"><span class="panel-title">各知识库文档分布</span></div>
        <table class="ops-table">
          <thead><tr><th>知识库</th><th>文档数</th><th>审核率</th><th>可检索率</th><th>健康分</th></tr></thead>
          <tbody>
            <tr v-for="row in healthRows" :key="row.name">
              <td class="col-name">{{ row.name }}</td>
              <td>{{ row.docCount }}</td>
              <td>{{ row.reviewRate }}%</td>
              <td>{{ row.retrievableRate }}%</td>
              <td><span class="score-pill" :class="row.healthScore >= 70 ? 'ok' : 'bad'">{{ row.healthScore }}</span></td>
            </tr>
            <tr v-if="!healthRows.length"><td colspan="5" class="empty-hint">暂无数据</td></tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ====== 首页大盘：热门内容 ====== -->
    <template v-else-if="section === 'popular'">
      <h2 class="page-title">热门内容</h2>
      <div class="chart-panel card">
        <div class="panel-head"><span class="panel-title">热门搜索榜</span><Icon name="fire" :size="14" class="info-hint" /></div>
        <div v-if="topTrending.length" class="trend-list">
          <div v-for="(t, i) in topTrending" :key="t.question" class="trend-item">
            <span class="trend-rank" :class="'rk-' + Math.min(i + 1, 3)">{{ i + 1 }}</span>
            <span class="trend-q">{{ t.question }}</span>
            <span class="trend-count">{{ t.count }}</span>
          </div>
        </div>
        <div v-else class="empty-hint">暂无热门搜索数据</div>
      </div>
    </template>

    <!-- ====== 其余分区：后端数据待接入 ====== -->
    <template v-else-if="section === 'analytics'">
      <h2 class="page-title">访问分析</h2>
      <ComingSoon icon="chart" title="访问分析" desc="访问趋势、会话量、平均停留时长等分析指标的后端采集接口尚未接入。" />
    </template>
    <template v-else-if="section === 'users'">
      <h2 class="page-title">用户统计</h2>
      <ComingSoon icon="users" title="用户统计" desc="用户活跃度、角色分布、新增趋势等统计的后端接口尚未接入。" />
    </template>
    <template v-else>
      <h2 class="page-title">系统公告</h2>
      <ComingSoon icon="bell" title="系统公告" desc="系统公告的发布与推送后端接口尚未接入。" note="公告中心页面骨架已就绪，接入后此处展示公告列表。" />
    </template>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ---- 指标卡行 ---- */
.stats-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
}
.stat-card {
  padding: 20px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.stat-card.tone-blue .stat-icon-wrap { background: var(--brand-soft); color: var(--brand); }
.stat-card.tone-cyan .stat-icon-wrap { background: var(--info-soft); color: var(--info); }
.stat-card.tone-green .stat-icon-wrap { background: var(--success-soft); color: var(--success); }
.stat-card.tone-orange .stat-icon-wrap { background: var(--warning-soft); color: var(--warning); }
.stat-card.tone-purple .stat-icon-wrap { background: var(--tag-soft); color: var(--node-tag); }
.stat-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
}
.stat-value {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.2;
  color: var(--text-primary);
}
.stat-delta {
  font-size: 12px;
  color: var(--text-tertiary);
}
.stat-delta.up { color: var(--success); }

/* ---- 图表行 ---- */
.charts-row {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 16px;
}
.panel-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
}
.panel-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}
.info-hint {
  color: var(--text-tertiary);
  cursor: pointer;
}

/* 热门搜索榜 */
.trend-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.trend-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 10px;
  border-radius: var(--radius-md);
  transition: background var(--dur-fast);
}
.trend-item:hover { background: var(--bg-hover); }
.trend-rank {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  background: var(--bg-subtle);
  color: var(--text-tertiary);
}
.trend-rank.rk-1 { background: var(--brand); color: #fff; }
.trend-rank.rk-2 { background: var(--brand-soft); color: var(--brand); }
.trend-rank.rk-3 { background: var(--warning-soft); color: var(--warning); }
.trend-q {
  flex: 1;
  font-size: 13.5px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.trend-count {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--brand);
  background: var(--brand-soft);
  padding: 2px 9px;
  border-radius: var(--radius-pill);
}

/* 饼图分类色（--cat-1..5 调色板）*/
.donut-seg.seg-1 { stroke: var(--cat-1); }
.donut-seg.seg-2 { stroke: var(--cat-2); }
.donut-seg.seg-3 { stroke: var(--cat-3); }
.donut-seg.seg-4 { stroke: var(--cat-4); }
.donut-seg.seg-5 { stroke: var(--cat-5); }
.legend-dot.seg-1 { background: var(--cat-1); }
.legend-dot.seg-2 { background: var(--cat-2); }
.legend-dot.seg-3 { background: var(--cat-3); }
.legend-dot.seg-4 { background: var(--cat-4); }
.legend-dot.seg-5 { background: var(--cat-5); }

/* 饼图面板 */
.pie-body {
  display: flex;
  align-items: center;
  gap: 24px;
}
.donut-chart {
  position: relative;
  width: 130px;
  height: 130px;
  flex-shrink: 0;
}
.donut-svg { width: 100%; height: 100%; }
.donut-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}
.donut-total {
  font-size: 20px;
  font-weight: 800;
  color: var(--text-primary);
}
.donut-label {
  font-size: 11px;
  color: var(--text-tertiary);
}
.pie-legend {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  flex-shrink: 0;
}
.legend-label {
  flex: 1;
  color: var(--text-secondary);
}
.legend-value {
  font-weight: 600;
  color: var(--text-primary);
  min-width: 48px;
  text-align: right;
}
.legend-pct {
  color: var(--text-tertiary);
  min-width: 44px;
  text-align: right;
  font-size: 12px;
}

/* ---- 健康概览表 ---- */
.chart-panel,
.pie-panel,
.ops-section {
  padding: 20px;
}
.ops-section { overflow: hidden; }
.warn-flag {
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  color: var(--warning);
  background: var(--warning-soft);
  padding: 3px 10px;
  border-radius: var(--radius-pill);
}
.ops-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.ops-table th {
  text-align: left;
  padding: 10px 14px;
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 12px;
  border-bottom: 1px solid var(--border);
}
.ops-table td {
  padding: 11px 14px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
}
.ops-table tr:last-child td { border-bottom: none; }
.col-name { font-weight: 600; }
.score-pill {
  display: inline-block;
  min-width: 30px;
  text-align: center;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-weight: 700;
  font-size: 12px;
}
.score-pill.ok { color: var(--success); background: var(--success-soft); }
.score-pill.bad { color: var(--danger); background: var(--danger-soft); }
.empty-hint {
  padding: 24px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
}
</style>
