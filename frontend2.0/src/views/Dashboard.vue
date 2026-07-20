<script setup lang="ts">
// 首页大盘 — 按 640(2).png 截图 1:1 还原。
// 5 张指标卡 + 访问趋势折线图 + 文档分类饼图 + 近期操作记录表。
defineProps<{ activeTab?: number }>()

import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'

const chartTab = ref('today')

// 指标卡数据
const stats = [
  { icon: 'doc', iconBg: '#E6F0FF', iconColor: '#014DB2', label: '文档总数', value: '24,567', delta: '+320', up: true },
  { icon: 'upload', iconBg: '#DBEAFE', iconColor: '#3B82F6', label: '今日新增文档', value: '128', delta: '+15', up: true },
  { icon: 'chat', iconBg: '#D1FAE5', iconColor: '#10B981', label: 'AI问答次数', value: '2,345', delta: '+234', up: true },
  { icon: 'search', iconBg: '#FEF3C7', iconColor: '#F59E0B', label: '用户搜索次数', value: '8,765', delta: '+567', up: true },
  { icon: 'users', iconBg: '#E0E7FF', iconColor: '#4F46E5', label: '活跃用户数', value: '1,234', delta: '+123', up: true },
]

// 饼图数据
const pieData = [
  { label: '产品文档', value: 8456, pct: '34.43%', color: '#3B82F6' },
  { label: '技术文档', value: 6789, pct: '27.66%', color: '#10B981' },
  { label: '培训资料', value: 4321, pct: '17.60%', color: '#F59E0B' },
  { label: '制度流程', value: 3210, pct: '13.08%', color: '#8B5CF6' },
  { label: '市场营销', value: 1791, pct: '7.30%', color: '#06B6D4' },
]

// 操作记录数据
const operations = [
  { time: '2024-05-20 14:30:25', user: '张三', type: '上传文档', typeIcon: 'upload', typeColor: '#3B82F6', content: '上传了文档《产品使用手册.pdf》', doc: '产品使用手册.pdf', docLink: '#' },
  { time: '2024-05-20 14:25:10', user: '李四', type: '更新文档', typeIcon: 'edit', typeColor: '#F59E0B', content: '更新了文档《企业安全管理制度.docx》', doc: '企业安全管理制度.docx', docLink: '#' },
  { time: '2024-05-20 14:20:45', user: '王五', type: '删除文档', typeIcon: 'trash', typeColor: '#EF4444', content: '删除了文档《旧版合同模板.docx》', doc: '旧版合同模板.docx', docLink: '#' },
  { time: '2024-05-20 14:15:30', user: '赵六', type: '用户登录', typeIcon: 'user', typeColor: '#8B5CF6', content: '用户登录系统', doc: '', docLink: '' },
  { time: '2024-05-20 14:10:18', user: '孙七', type: 'AI问答', typeIcon: 'chat', typeColor: '#06B6D4', content: '通过AI问答获取了答案', doc: '', docLink: '' },
]
</script>

<template>
  <div class="dashboard">
    <!-- ====== Row 1: 指标卡 ====== -->
    <div class="stats-row">
      <div v-for="s in stats" :key="s.label" class="stat-card card">
        <div class="stat-icon-wrap" :style="{ background: s.iconBg }">
          <Icon :name="s.icon" :size="22" :style="{ color: s.iconColor }" />
        </div>
        <div class="stat-info">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-delta" :class="{ up: s.up }">
            较昨日 {{ s.delta }} {{ s.up ? '↑' : '↓' }}
          </div>
        </div>
      </div>
    </div>

    <!-- ====== Row 2: 图表区（左右分栏）====== -->
    <div class="charts-row">
      <!-- 左：访问趋势折线图 -->
      <div class="chart-panel card">
        <div class="panel-head">
          <span class="panel-title">访问趋势</span>
          <Icon name="alert" :size="14" class="info-hint" />
        </div>
        <!-- Tab 切换 -->
        <div class="chart-tabs">
          <button v-for="t in ['今日', '近7日', '近30日']" :key="t"
            class="chart-tab" :class="{ active: (t === '今日' && chartTab === 'today') || (t === '近7日' && chartTab === 'week') || (t === '近30日' && chartTab === 'month') }"
            @click="chartTab = t.toLowerCase()">{{ t }}</button>
        </div>
        <!-- 折线图 SVG -->
        <svg viewBox="0 0 600 220" class="line-chart" preserveAspectRatio="none">
          <!-- Y轴网格线 -->
          <g class="grid-lines">
            <line x1="44" y1="16" x2="584" y2="16" stroke="#EEF2F8" stroke-width="1" />
            <line x1="44" y1="60" x2="584" y2="60" stroke="#EEF2F8" stroke-width="1" />
            <line x1="44" y1="104" x2="584" y2="104" stroke="#EEF2F8" stroke-width="1" />
            <line x1="44" y1="148" x2="584" y2="148" stroke="#EEF2F8" stroke-width="1" />
            <line x1="44" y1="192" x2="584" y2="192" stroke="#EEF2F8" stroke-width="1" />
          </g>
          <!-- Y轴标签 -->
          <g class="y-labels" fill="#8A97AC" font-size="11">
            <text x="36" y="20" text-anchor="end">1,800</text>
            <text x="36" y="64" text-anchor="end">1,500</text>
            <text x="36" y="108" text-anchor="end">1,200</text>
            <text x="36" y="152" text-anchor="end">900</text>
            <text x="36" y="196" text-anchor="end">300</text>
            <text x="36" y="210" text-anchor="end">0</text>
          </g>
          <!-- X轴标签 -->
          <g class="x-labels" fill="#8A97AC" font-size="11">
            <text x="50" y="212" text-anchor="middle">00:00</text>
            <text x="96" y="212" text-anchor="middle">03:00</text>
            <text x="142" y="212" text-anchor="middle">06:00</text>
            <text x="188" y="212" text-anchor="middle">09:00</text>
            <text x="235" y="212" text-anchor="middle">12:00</text>
            <text x="281" y="212" text-anchor="middle">15:00</text>
            <text x="327" y="212" text-anchor="middle">18:00</text>
            <text x="373" y="212" text-anchor="middle">21:00</text>
            <text x="420" y="212" text-anchor="middle">24:00</text>
          </g>
          <!-- 折线 + 面积 -->
          <defs>
            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#014DB2" stop-opacity="0.15" />
              <stop offset="100%" stop-color="#014DB2" stop-opacity="0.02" />
            </linearGradient>
          </defs>
          <path d="M50,190 L73,186 L96,178 L119,172 L142,168 L165,162 L188,150 L211,138 L235,118 L258,95 L281,75 L304,68 L327,78 L350,92 L373,115 L396,140 L420,160 L443,175 L466,184 L489,188 L512,191 L535,189 L558,192 L580,195"
                fill="none" stroke="#014DB2" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M50,190 L73,186 L96,178 L119,172 L142,168 L165,162 L188,150 L211,138 L235,118 L258,95 L281,75 L304,68 L327,78 L350,92 L373,115 L396,140 L420,160 L443,175 L466,184 L489,188 L512,191 L535,189 L558,192 L580,195 L580,196 L50,196Z"
            fill="url(#areaGrad)" />
          <!-- 数据点 -->
          <g fill="#014DB2">
            <circle cx="50" cy="190" r="3.5" /><circle cx="96" cy="178" r="3.5" /><circle cx="142" cy="168" r="3.5" />
            <circle cx="188" cy="150" r="3.5" /><circle cx="235" cy="118" r="3.5" /><circle cx="281" cy="75" r="3.5" />
            <circle cx="327" cy="78" r="3.5" /><circle cx="373" cy="115" r="3.5" /><circle cx="420" cy="160" r="3.5" />
            <circle cx="466" cy="184" r="3.5" /><circle cx="512" cy="191" r="3.5" /><circle cx="558" cy="192" r="3.5" />
          </g>
          <!-- 白色内圈（截图风格）-->
          <g fill="#fff">
            <circle cx="50" cy="190" r="1.5" /><circle cx="96" cy="178" r="1.5" /><circle cx="142" cy="168" r="1.5" />
            <circle cx="188" cy="150" r="1.5" /><circle cx="235" cy="118" r="1.5" /><circle cx="281" cy="75" r="1.5" />
            <circle cx="327" cy="78" r="1.5" /><circle cx="373" cy="115" r="1.5" /><circle cx="420" cy="160" r="1.5" />
            <circle cx="466" cy="184" r="1.5" /><circle cx="512" cy="191" r="1.5" /><circle cx="558" cy="192" r="1.5" />
          </g>
        </svg>
      </div>

      <!-- 右：文档分类占比饼图 -->
      <div class="pie-panel card">
        <div class="panel-head">
          <span class="panel-title">文档分类占比</span>
          <Icon name="alert" :size="14" class="info-hint" />
        </div>
        <div class="pie-body">
          <div class="donut-chart">
            <!-- SVG 环形图 -->
            <svg viewBox="0 0 120 120" class="donut-svg">
              <!-- 产品文档 34.43% = 124° -->
              <circle cx="60" cy="60" r="46" fill="none" stroke="#3B82F6" stroke-width="18"
                stroke-dasharray="100 188.5" transform="rotate(-90 60 60)" />
              <!-- 技术文档 27.66% = 99.6° -->
              <circle cx="60" cy="60" r="46" fill="none" stroke="#10B981" stroke-width="18"
                stroke-dasharray="79.7 208.8" stroke-dashoffset="-100" transform="rotate(-90 60 60)" />
              <!-- 培训资料 17.60% = 63.4° -->
              <circle cx="60" cy="60" r="46" fill="none" stroke="#F59E0B" stroke-width="18"
                stroke-dasharray="50.7 237.8" stroke-dashoffset="-179.7" transform="rotate(-90 60 60)" />
              <!-- 制度流程 13.08% = 47.1° -->
              <circle cx="60" cy="60" r="46" fill="none" stroke="#8B5CF6" stroke-width="18"
                stroke-dasharray="37.7 250.8" stroke-dashoffset="-230.4" transform="rotate(-90 60 60)" />
              <!-- 市场营销 7.30% = 26.3° -->
              <circle cx="60" cy="60" r="46" fill="none" stroke="#06B6D4" stroke-width="18"
                stroke-dasharray="21 262.5" stroke-dashoffset="-268.1" transform="rotate(-90 60 60)" />
            </svg>
            <div class="donut-center">
              <div class="donut-total">24,567</div>
              <div class="donut-label">文档总数</div>
            </div>
          </div>
          <!-- 图例 -->
          <div class="pie-legend">
            <div v-for="p in pieData" :key="p.label" class="legend-item">
              <span class="legend-dot" :style="{ background: p.color }"></span>
              <span class="legend-label">{{ p.label }}</span>
              <span class="legend-value">{{ p.value.toLocaleString() }}</span>
              <span class="legend-pct">{{ p.pct }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== Row 3: 近期操作记录 ====== -->
    <div class="ops-section card">
      <div class="panel-head">
        <span class="panel-title">近期操作记录</span>
        <a href="#" class="view-more">查看更多</a>
      </div>
      <table class="ops-table">
        <thead>
          <tr>
            <th>操作时间</th><th>操作用户</th><th>操作类型</th><th>操作内容</th><th>相关文档</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(op, i) in operations" :key="i">
            <td class="col-time">{{ op.time }}</td>
            <td>{{ op.user }}</td>
            <td>
              <span class="type-badge" :style="{ color: op.typeColor, background: op.typeColor + '18' }">
                <Icon :name="op.typeIcon" :size="12" />{{ op.type }}
              </span>
            </td>
            <td class="col-content">{{ op.content }}</td>
            <td>
              <a v-if="op.doc" :href="op.docLink" class="doc-link">{{ op.doc }}</a>
              <span v-else class="no-doc">-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 收起菜单 -->
    <button class="collapse-btn">
      <Icon name="collapse" :size="14" /> 收起菜单
    </button>
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
.stat-delta.up { color: #EF4444; }

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

.chart-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
}
.chart-tab {
  padding: 5px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--dur-fast);
  border: none;
  font-family: inherit;
}
.chart-tab:hover { background: var(--bg-hover); }
.chart-tab.active {
  background: var(--brand);
  color: #fff;
}

.line-chart {
  width: 100%;
  height: 220px;
}

/* ---- 饼图面板 ---- */
.pie-body {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 8px 0;
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

/* ---- 操作记录表 ---- */
.ops-section { overflow: hidden; }
.view-more {
  margin-left: auto;
  font-size: 13px;
  color: var(--brand);
  text-decoration: none;
}
.view-more:hover { text-decoration: underline; }

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
.col-time { color: var(--text-tertiary); white-space: nowrap; }
.col-content { max-width: 320px; }

.type-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 500;
}
.doc-link {
  color: var(--brand);
  text-decoration: none;
}
.doc-link:hover { text-decoration: underline; }
.no-doc { color: var(--text-tertiary); }

.collapse-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  transition: all var(--dur-fast);
  width: fit-content;
}
.collapse-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
</style>
