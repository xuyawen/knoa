<script setup lang="ts">
// 首页大盘 — 参考 640(2).png 原型：5 指标卡（带涨跌）+ 趋势折线图 + 分类饼图 + 操作记录
// 数据来源：knowledge store（真实）+ 模拟趋势/操作记录（后端未接入）
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useKnowledgeStore } from '@/stores/knowledge'
import Icon from '@/components/ui/Icon.vue'
import ComingSoon from '@/components/ui/ComingSoon.vue'

const kb = useKnowledgeStore()
const { bases, health, trending } = storeToRefs(kb)

const props = defineProps<{ section?: string }>()
const section = computed(() => props.section ?? 'overview')

onMounted(() => { if (!kb.loaded) kb.load() })

// ── 真实指标 ──
const totalDocs = computed(() => bases.value.reduce((s, b) => s + b.documentCount, 0))
const pendingDocs = computed(() => bases.value.reduce((s, b) => s + b.pendingCount, 0))

// ── 5 项指标卡（参考原型 #2）──
const statCards = computed(() => [
  {
    icon: 'doc', color: '#3b82f6', bg: 'rgba(59,130,246,0.10)',
    label: '文档总数', value: totalDocs.value.toLocaleString(),
    delta: '+320', up: true,
  },
  {
    icon: 'plus', color: '#06b6d4', bg: 'rgba(6,182,212,0.10)',
    label: '今日新增文档', value: String(pendingDocs.value || Math.floor(Math.random() * 20) + 1),
    delta: '+15', up: true,
  },
  {
    icon: 'sparkles', color: '#8b5cf6', bg: 'rgba(139,92,246,0.10)',
    label: 'AI 问答次数', value: '2,345',
    delta: '+234', up: true,
  },
  {
    icon: 'search', color: '#3b82f6', bg: 'rgba(59,130,246,0.10)',
    label: '用户搜索次数', value: '8,765',
    delta: '+567', up: true,
  },
  {
    icon: 'users', color: '#8b5cf6', bg: 'rgba(139,92,246,0.10)',
    label: '活跃用户数', value: '1,234',
    delta: '+123', up: true,
  },
])

// ── 饼图：文档分类占比 ──
const CIRC = 2 * Math.PI * 46
const pieTotal = computed(() => totalDocs.value)
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
    return { label: b.name, value: v, pct: (frac * 100).toFixed(1), seg: palette[i % 5], dash, offset }
  })
})

// ── 热门搜索榜（真实）──
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

// ── 趋势折线图数据（模拟，后端待接入）──
type TrendRange = 'today' | 'week' | 'month'
const trendRange = ref<TrendRange>('today')
// 模拟 24 小时 / 7 天 / 30 天的数据点
function genTrendPoints(n: number, base: number, variance: number) {
  const pts: number[] = []
  let v = base
  for (let i = 0; i < n; i++) {
    v += (Math.random() - 0.35) * variance
    v = Math.max(base * 0.15, v)
    pts.push(Math.round(v))
  }
  return pts
}
const trendMap = computed<Record<TrendRange, { points: number[]; labels: string[]; max: number }>>(() => ({
  today:   { points: genTrendPoints(24, 80, 60), labels: Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2,'0')}:00`), max: 1800 },
  week:    { points: genTrendPoints(7, 400, 200), labels: ['周一','周二','周三','周四','周五','周六','周日'], max: 1200 },
  month:   { points: genTrendPoints(30, 350, 180), labels: Array.from({ length: 30 }, (_, i) => `${i + 1}日`), max: 1000 },
}))
const activeTrend = computed(() => trendMap.value[trendRange.value])
const chartH = 220
const chartW = 520

// SVG 折线路径
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
// 渐变区域路径（闭合）
const areaPath = computed(() => {
  const p = linePath.value
  if (!p) return ''
  const lastX = chartW
  return `${p} L ${lastX.toFixed(1)} ${chartH} L 0 ${chartH} Z`
})
// 数据点坐标
const dotCoords = computed(() =>
  activeTrend.value.points.map((v, i) => {
    const stepX = chartW / (activeTrend.value.points.length - 1 || 1)
    const padY = 20; const drawH = chartH - padY * 2
    return { cx: (i * stepX).toFixed(1), cy: (chartH - padY - (v / activeTrend.value.max) * drawH).toFixed(1), val: v }
  }),
)

// ── 操作记录（模拟）──
const activityLog = ref([
  { time: '2024-05-20 14:30:25', user: '张三', type: '上传文档', content: '上传了文档《产品使用手册.pdf》', file: '产品使用手册.pdf' },
  { time: '2024-05-20 14:25:10', user: '李四', type: '更新文档', content: '更新了文档《企业安全管理制度.docx》', file: '企业安全管理制度.docx' },
  { time: '2024-05-20 14:20:45', user: '王五', type: '删除文档', content: '删除了文档《旧版合同模板.docx》', file: '旧版合同模板.docx' },
  { time: '2024-05-20 14:15:30', user: '赵六', type: '用户登录', content: '用户登录系统', file: '' },
  { time: '2024-05-20 14:10:18', user: '孙七', type: 'AI 问答', content: '通过 AI 问答获取了答案', file: '' },
])

const ACT_ICONS: Record<string, string> = {
  '上传文档': 'upload', '更新文件': 'edit', '删除文档': 'trash',
  '更新文档': 'edit', '用户登录': 'user-circle', 'AI 问答': 'sparkles',
}
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
              <!-- Y轴网格线 -->
              <g class="grid-lines">
                <line v-for="n in 5" :key="n" :x1="0" :y1="(n-1)*(chartH/4)" :x2="chartW" :y2="(n-1)*(chartH/4)" stroke="var(--border)" stroke-dasharray="4,4" />
              </g>
              <!-- 面积 -->
              <path :d="areaPath" fill="url(#areaGrad)" />
              <!-- 折线 -->
              <path :d="linePath" fill="none" stroke="var(--brand)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
              <!-- 数据点 -->
              <g v-for="(d, i) in dotCoords" :key="i">
                <circle :cx="d.cx" :cy="d.cy" r="3.5" fill="var(--bg-elevated, var(--bg-surface))" stroke="var(--brand)" stroke-width="1.8" />
                <title>{{ activeTrend.labels[i] }} · {{ d.val }}</title>
              </g>
            </svg>
            <!-- X轴标签 -->
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
            </div>
          </div>
        </div>
      </div>

      <!-- Row 3: 近期操作记录 -->
      <div class="ops-section card">
        <div class="panel-head">
          <span class="panel-title">近期操作记录</span>
          <a href="#" class="view-more" @click.prevent>查看更多</a>
        </div>
        <table class="ops-table">
          <thead>
            <tr><th>操作时间</th><th>操作用户</th><th>操作类型</th><th>操作内容</th><th>相关文档</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in activityLog" :key="row.time + row.user">
              <td class="col-time">{{ row.time }}</td>
              <td>{{ row.user }}</td>
              <td>
                <span class="act-tag">
                  <Icon :name="ACT_ICONS[row.type] || 'file'" :size="12" />
                  {{ row.type }}
                </span>
              </td>
              <td class="col-content">{{ row.content }}</td>
              <td>
                <a v-if="row.file" href="#" class="doc-link" @click.prevent>{{ row.file }}</a>
                <span v-else class="na">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ====== docs 分区 ====== -->
    <template v-else-if="section === 'docs'">
      <h2 class="page-title">文档统计</h2>
      <div class="stats-row">
        <div class="stat-card card"><div class="sc-icon" style="background:rgba(59,130,246,.1);color:#3b82f6"><Icon name="doc" :size="22"/></div><div class="sc-body"><div class="sc-label">文档总数</div><div class="sc-value">{{ totalDocs.toLocaleString() }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:rgba(34,197,94,.1);color:#22c55e"><Icon name="check" :size="22"/></div><div class="sc-body"><div class="sc-label">已审核</div><div class="sc-value">{{ (totalDocs-pendingDocs).toLocaleString() }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:rgba(245,158,11,.1);color:#f59e0b"><Icon name="alert" :size="22"/></div><div class="sc-body"><div class="sc-label">待复核</div><div class="sc-value">{{ pendingDocs }}</div></div></div>
        <div class="stat-card card"><div class="sc-icon" style="background:rgba(139,92,246,.1);color:#8b5cf6"><Icon name="folder" :size="22"/></div><div class="sc-body"><div class="sc-label">知识库数</div><div class="sc-value">{{ bases.length }}</div></div></div>
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

    <!-- ====== 占位分区 ====== -->
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
.doc-link { color:var(--brand); text-decoration:none; font-size:12.5px; }
.doc-link:hover { text-decoration:underline; }
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

@media (max-width:1024px){
  .stats-row{grid-template-columns:repeat(3,1fr)}
  .charts-row{grid-template-columns:1fr}
}
@media (max-width:720px){ .stats-row{grid-template-columns:repeat(2,1fr)} }
</style>
