<script setup lang="ts">
// 首页大盘（对应截图 #2）：指标卡 + 趋势折线 + 分类饼图 + 操作记录表。
// 界面壳阶段：全部为静态示例数据，功能接入后由聚合接口替换。
import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'

const range = ref<'today' | '7d' | '30d'>('7d')

const stats = [
  { label: '文档总数', value: '24,567', delta: '+3.2%', up: true, icon: 'doc' },
  { label: '今日新增文档', value: '128', delta: '+12', up: true, icon: 'upload' },
  { label: 'AI 问答次数', value: '2,345', delta: '+18.4%', up: true, icon: 'chat' },
  { label: '用户搜索次数', value: '8,765', delta: '+5.1%', up: true, icon: 'search' },
  { label: '活跃用户数', value: '1,234', delta: '-1.3%', up: false, icon: 'user' },
]

// 折线示例点（7 日）
const trend = [38, 52, 47, 63, 58, 72, 81]
const maxV = Math.max(...trend)
const points = trend
  .map((v, i) => {
    const x = 40 + (i * (620 / (trend.length - 1)))
    const y = 200 - (v / maxV) * 160
    return `${x},${y}`
  })
  .join(' ')

const pie = [
  { name: '产品手册', value: 38, color: 'var(--brand)' },
  { name: '规章制度', value: 26, color: 'var(--success)' },
  { name: '培训资料', value: 19, color: 'var(--node-tag)' },
  { name: '项目文档', value: 11, color: 'var(--node-category)' },
  { name: '其他', value: 6, color: 'var(--text-tertiary)' },
]
const pieTotal = pie.reduce((s, p) => s + p.value, 0)

const ops = [
  { user: '张伟', action: '上传文档', target: '《2026 数据安全管理制度》', time: '09:42' },
  { user: '李娜', action: '更新文档', target: '《产品使用手册 v3.2》', time: '09:15' },
  { user: '王芳', action: '删除文档', target: '《临时会议纪要》', time: '08:51' },
  { user: '陈强', action: '用户登录', target: '—', time: '08:30' },
  { user: '赵敏', action: 'AI 问答', target: '"如何申请权限？"', time: '08:12' },
]
</script>

<template>
  <div class="page fade-up">
    <header class="page-head">
      <div class="flex items-center">
        <h1 class="page-title">首页大盘</h1>
        <span class="todo-flag"><Icon name="sparkles" :size="12" />界面壳 · 示例数据</span>
      </div>
      <p class="page-sub">知识库整体运行概览与关键指标监测</p>
    </header>

    <!-- 指标卡 -->
    <div class="stat-grid">
      <div v-for="s in stats" :key="s.label" class="card stat">
        <span class="stat-ic"><Icon :name="s.icon" :size="18" /></span>
        <div class="stat-body">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-delta" :class="s.up ? 'up' : 'down'">
            {{ s.delta }}
            <span class="text-xs text-tertiary">较昨日</span>
          </div>
        </div>
      </div>
    </div>

    <div class="charts">
      <!-- 折线 -->
      <div class="card chart-card">
        <div class="chart-head">
          <h3>访问趋势</h3>
          <div class="seg">
            <button :class="{ on: range === 'today' }" @click="range = 'today'">今日</button>
            <button :class="{ on: range === '7d' }" @click="range = '7d'">近 7 日</button>
            <button :class="{ on: range === '30d' }" @click="range = '30d'">近 30 日</button>
          </div>
        </div>
        <svg class="line" viewBox="0 0 700 220" preserveAspectRatio="none">
          <defs>
            <linearGradient id="lg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="var(--brand)" stop-opacity="0.22" />
              <stop offset="1" stop-color="var(--brand)" stop-opacity="0" />
            </linearGradient>
          </defs>
          <line v-for="i in 4" :key="i" x1="40" :x2="660" :y1="40 + (i - 1) * 53" :y2="40 + (i - 1) * 53" stroke="var(--border)" stroke-width="1" />
          <polygon :points="`40,200 ${points} 660,200`" fill="url(#lg)" />
          <polyline :points="points" fill="none" stroke="var(--brand)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
          <circle v-for="(p, i) in points.split(' ')" :key="i" :cx="p.split(',')[0]" :cy="p.split(',')[1]" r="3.5" fill="var(--bg-surface)" stroke="var(--brand)" stroke-width="2" />
        </svg>
      </div>

      <!-- 饼图 -->
      <div class="card chart-card">
        <div class="chart-head"><h3>文档分类占比</h3></div>
        <div class="pie-row">
          <svg class="pie" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="52" fill="none" stroke="var(--border)" stroke-width="18" />
            <circle
              v-for="(p, i) in pie"
              :key="p.name"
              cx="60" cy="60" r="52" fill="none"
              :stroke="p.color" stroke-width="18"
              :stroke-dasharray="`${(p.value / pieTotal) * 327} 327`"
              :stroke-dashoffset="-(pie.slice(0, i).reduce((s, x) => s + x.value, 0) / pieTotal) * 327"
              transform="rotate(-90 60 60)"
              stroke-linecap="butt"
            />
          </svg>
          <ul class="legend">
            <li v-for="p in pie" :key="p.name">
              <span class="dot" :style="{ background: p.color }" />
              <span class="lg-name">{{ p.name }}</span>
              <span class="lg-val">{{ p.value }}%</span>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 操作记录 -->
    <div class="card ops">
      <div class="ops-head"><h3>近期操作记录</h3></div>
      <table class="ops-table">
        <thead>
          <tr><th>操作用户</th><th>操作类型</th><th>操作对象</th><th>时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="(o, i) in ops" :key="i">
            <td>{{ o.user }}</td>
            <td><span class="badge" :class="`badge-${o.action.includes('删除') ? 'danger' : 'info'}`">{{ o.action }}</span></td>
            <td class="truncate">{{ o.target }}</td>
            <td class="text-tertiary">{{ o.time }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.stat {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
}
.stat-ic {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: var(--brand-soft);
  color: var(--brand);
  flex-shrink: 0;
}
.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
}
.stat-value {
  font-size: 23px;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin: 2px 0;
}
.stat-delta {
  font-size: 12px;
  font-weight: 600;
}
.stat-delta.up { color: var(--success); }
.stat-delta.down { color: var(--danger); }
.stat-delta .text-tertiary { font-weight: 400; margin-left: 4px; }

.charts {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.chart-card { padding: 18px 20px; }
.chart-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.chart-head h3 { margin: 0; font-size: 15px; font-weight: 600; }
.seg {
  display: inline-flex;
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  padding: 3px;
  gap: 2px;
}
.seg button {
  padding: 4px 11px;
  font-size: 12px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  transition: all var(--dur-fast);
}
.seg button.on {
  background: var(--bg-surface);
  color: var(--brand);
  font-weight: 600;
  box-shadow: var(--shadow-card);
}
.line { width: 100%; height: 220px; }

.pie-row { display: flex; align-items: center; gap: 18px; }
.pie { width: 130px; height: 130px; flex-shrink: 0; }
.legend { list-style: none; padding: 0; margin: 0; flex: 1; display: flex; flex-direction: column; gap: 8px; }
.legend li { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.dot { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
.lg-name { color: var(--text-secondary); }
.lg-val { margin-left: auto; font-weight: 600; }

.ops { padding: 18px 20px; }
.ops-head { margin-bottom: 12px; }
.ops-head h3 { margin: 0; font-size: 15px; font-weight: 600; }
.ops-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.ops-table th {
  text-align: left;
  padding: 9px 12px;
  color: var(--text-tertiary);
  font-weight: 500;
  border-bottom: 1px solid var(--border);
}
.ops-table td {
  padding: 11px 12px;
  border-bottom: 1px solid var(--border);
}
.ops-table tr:last-child td { border-bottom: none; }

@media (max-width: 1080px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .charts { grid-template-columns: 1fr; }
}
</style>
