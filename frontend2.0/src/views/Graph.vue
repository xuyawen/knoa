<script setup lang="ts">
// 知识图谱 — 按 640(6).png 截图 1:1 还原。
defineProps<{ activeTab?: number }>()

import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'

const graphQuery = ref('')

// 图谱统计
const stats = [
  { label: '节点总数', value: '1,245', icon: 'doc', color: '#3B82F6' },
  { label: '文档节点', value: '612', icon: 'doc', color: '#3B82F6' },
  { label: '标签', value: '156', icon: 'tag', color: '#8B5CF6' },
  { label: '关系总数', value: '3,672', icon: 'link', color: '#10B981' },
  { label: '知识点', value: '423', icon: 'fire', color: '#10B981' },
  { label: '业务分类', value: '54', icon: 'folder', color: '#F59E0B' },
]

// 热门节点 Top 5
const hotNodes = [
  { name: '数字化转型规划', type: 'doc', color: '#3B82F6', count: 362 },
  { name: '技术架构设计', type: 'doc', color: '#3B82F6', count: 286 },
  { name: '业务流程优化', type: 'knowledge', color: '#10B981', count: 286 },
  { name: '数据治理体系', type: 'knowledge', color: '#10B981', count: 254 },
  { name: '组织架构升级', type: 'tag', color: '#8B5CF6', count: 198 },
]

// 最近新增节点
const recentNodes = [
  { name: '制造业转型案例.docx', type: 'doc', color: '#3B82F6', time: '2024-05-20 14:30' },
  { name: '技术选型方案.xlsx', type: 'excel', color: '#10B981', time: '2024-05-20 10:15' },
  { name: '大行业案例.pptx', type: 'pptx', color: '#F59E0B', time: '2024-05-19 16:45' },
  { name: '数字化转型白皮书.pdf', type: 'pdf', color: '#EF4444', time: '2024-05-19 09:20' },
]
</script>

<template>
  <div class="graph-page">
    <!-- 页面标题 -->
    <h2 class="page-title">知识图谱</h2>

    <!-- ====== 工具栏 ====== -->
    <div class="graph-toolbar card">
      <div class="toolbar-left">
        <div class="g-search">
          <input v-model="graphQuery" type="text" placeholder="请输入关键词搜索图谱..." class="g-input" />
          <Icon name="search" :size="15" class="g-search-icon" />
        </div>
        <div class="g-filter">节点类型 <span>全部</span> <Icon name="chevron-down" :size="11" /></div>
        <div class="g-filter">业务分类 <span>全部</span> <Icon name="chevron-down" :size="11" /></div>
        <div class="g-date">
          创建时间
          <Icon name="calendar" :size="13" style="margin-left:4px"/>
          <span class="date-ph">选择日期范围</span>
        </div>
        <button class="btn btn-ghost btn-sm g-reset">重置</button>
      </div>
      <div class="toolbar-right">
        <button class="btn btn-primary btn-sm"><Icon name="search" :size="13" /> 搜索</button>
        <button class="btn btn-ghost btn-sm"><Icon name="export" :size="13" /> 导出图谱</button>
      </div>
    </div>

    <!-- ====== 主区：图布 + 右侧面板 ====== -->
    <div class="graph-body">
      <!-- 左：图布 -->
      <div class="canvas-area card">
        <svg viewBox="0 0 780 480" class="force-graph" preserveAspectRatio="xMidYMid meet">
          <!-- 定义箭头标记 -->
          <defs>
            <marker id="arrowRef" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto-start-reverse" markerUnits="strokeWidth">
              <path d="M0,0 L0,6 L8,3 z" fill="#94A3B8" />
            </marker>
            <marker id="arrowInc" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto-start-reverse" markerUnits="strokeWidth">
              <path d="M0,0 L0,6 L8,3 z" fill="#CBD5E1" />
            </marker>
            <!-- 节点发光效果 -->
            <filter id="glow">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          <!-- ====== 连线（先画，在底层）====== -->
          <g class="edges" stroke-width="1.5" fill="none">
            <!-- 引用关系（实线+箭头） -->
            <path d="M220,160 Q280,140 340,200" stroke="#94A3B8" marker-end="url(#arrowRef)" />
            <text x="265" y="142" class="edge-label" fill="#8A97AC">引用</text>

            <path d="M560,155 Q500,150 430,200" stroke="#94A3B8" marker-end="url(#arrowRef)" />
            <text x="498" y="142" class="edge-label" fill="#8A97AC">引用</text>

            <path d="M260,320 Q310,290 355,250" stroke="#94A3B8" marker-end="url(#arrowRef)" />
            <text x="292" y="272" class="edge-label" fill="#8A97AC">引用</text>

            <path d="M520,320 Q480,285 440,248" stroke="#94A3B8" marker-end="url(#arrowRef)" />
            <text x="482" y="272" class="edge-label" fill="#8A97AC">引用</text>

            <!-- 包含关系（实线） -->
            <line x1="390" y1="228" x2="270" y2="175" stroke="#CBD5E1" />
            <text x="320" y="193" class="edge-label" fill="#8A97AC">包含</text>

            <line x1="400" y1="228" x2="520" y2="170" stroke="#CBD5E1" />
            <text x="458" y="193" class="edge-label" fill="#8A97AC">包含</text>

            <line x1="385" y1="255" x2="275" y2="305" stroke="#CBD5E1" />
            <text x="315" y="275" class="edge-label" fill="#8A97AC">包含</text>

            <line x1="405" y1="255" x2="525" y2="308" stroke="#CBD5E1" />
            <text x="468" y="275" class="edge-label" fill="#8A97AC">包含</text>

            <line x1="395" y1="255" x2="395" y2="350" stroke="#CBD5E1" />
            <text x="405" y="305" class="edge-label" fill="#8A97AC">属于</text>

            <line x1="450" y1="370" x2="505" y2="365" stroke="#CBD5E1" />
            <text x="472" y="362" class="edge-label" fill="#8A97AC">包含</text>

            <line x1="340" y1="370" x2="285" y2="368" stroke="#CBD5E1" />
            <text x="302" y="362" class="edge-label" fill="#8A97AC">关联</text>

            <!-- 关联关系（虚线） -->
            <path d="M200,195 Q170,240 190,300" stroke="#94A3B8" stroke-dasharray="5,4" />
            <text x="165" y="250" class="edge-label" fill="#8A97AC">关联</text>

            <path d="M205,185 Q165,145 180,105" stroke="#94A3B8" stroke-dasharray="5,4" />
            <text x="148" y="142" class="edge-label" fill="#8A97AC">关联</text>

            <path d="M585,190 Q620,235 600,295" stroke="#94A3B8" stroke-dasharray="5,4" />
            <text x="612" y="245" class="edge-label" fill="#8A97AC">关联</text>

            <path d="M580,178 Q618,138 600,100" stroke="#94A3B8" stroke-dasharray="5,4" />
            <text x="615" y="135" class="edge-label" fill="#8A97AC">关联</text>

            <path d="M230,348 Q210,390 245,420" stroke="#94A3B8" stroke-dasharray="5,4" />
            <text x="212" y="390" class="edge-label" fill="#8A97AC">关联</text>

            <path d="M555,348 Q580,390 545,420" stroke="#94A3B8" stroke-dasharray="5,4" />
            <text x="572" y="390" class="edge-label" fill="#8A97AC">关联</text>

            <path d="M330,398 Q360,425 380,418" stroke="#94A3B8" stroke-dasharray="5,4" />
            <text x="342" y="422" class="edge-label" fill="#8A97AC">关联</text>

            <path d="M465,398 Q435,425 415,418" stroke="#94A3B8" stroke-dasharray="5,4" />
            <text x="432" y="422" class="edge-label" fill="#8A97AC">关联</text>
          </g>

          <!-- ====== 节点 ====== -->
          <g class="nodes">
            <!-- 中心节点：企业数字化转型蓝图 (文档/蓝) -->
            <g transform="translate(395, 225)" filter="url(#glow)">
              <rect x="-42" y="-22" width="84" height="44" rx="10" fill="#3B82F6" />
              <rect x="-41" y="-21" width="82" height="42" rx="9" fill="none" stroke="#fff" stroke-opacity=".3" stroke-width="1" />
              <text y="-2" text-anchor="middle" fill="#fff" font-size="11" font-weight="700">企业数字化转型蓝图</text>
              <text y="12" text-anchor="middle" fill="rgba(255,255,255,.75)" font-size="9">(Document)</text>
            </g>

            <!-- 周围节点 — 上层 -->
            <g transform="translate(200, 160)">
              <rect x="-38" y="-17" width="76" height="34" rx="8" fill="#fff" stroke="#3B82F6" stroke-width="1.5" />
              <circle cx="-28" cy="0" r="8" fill="#E6F0FF" /><text x="-28" y="3.5" text-anchor="middle" fill="#3B82F6" font-size="9" font-weight="700">W</text>
              <text x="6" y="4" text-anchor="middle" fill="#334155" font-size="10.5" font-weight="600">数字化转型白皮书.pdf</text>
            </g>
            <g transform="translate(570, 155)">
              <rect x="-52" y="-17" width="104" height="34" rx="8" fill="#fff" stroke="#3B82F6" stroke-width="1.5" />
              <circle cx="-42" cy="0" r="8" fill="#E6F0FF" /><text x="-42" y="3.5" text-anchor="middle" fill="#3B82F6" font-size="9" font-weight="700">W</text>
              <text x="8" y="4" text-anchor="middle" fill="#334155" font-size="10.5" font-weight="600">制造业转型策略.docx</text>
            </g>

            <!-- 中层左右 -->
            <g transform="translate(250, 320)">
              <rect x="-46" y="-17" width="92" height="34" rx="8" fill="#fff" stroke="#3B82F6" stroke-width="1.5" />
              <circle cx="-36" cy="0" r="8" fill="#D1FAE5" /><text x="-36" y="3.5" text-anchor="middle" fill="#10B981" font-size="9" font-weight="700">X</text>
              <text x="8" y="4" text-anchor="middle" fill="#334155" font-size="10.5" font-weight="600">技术选型方案.xlsx</text>
            </g>
            <g transform="translate(540, 320)">
              <rect x="-54" y="-17" width="108" height="34" rx="8" fill="#fff" stroke="#F59E0B" stroke-width="1.5" />
              <circle cx="-44" cy="0" r="8" fill="#FEF3C7" /><text x="-44" y="3.5" text-anchor="middle" fill="#D97706" font-size="9" font-weight="700">P</text>
              <text x="8" y="4" text-anchor="middle" fill="#334155" font-size="10.5" font-weight="600">零壹行业案例.pptx</text>
            </g>

            <!-- 知识点（绿） -->
            <g transform="translate(175, 188)">
              <rect x="-36" y="-14" width="72" height="28" rx="14" fill="#D1FAE5" stroke="#10B981" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#065F46" font-size="10" font-weight="600">技术架构</text>
            </g>
            <g transform="translate(605, 182)">
              <rect x="-36" y="-14" width="72" height="28" rx="14" fill="#D1FAE5" stroke="#10B981" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#065F46" font-size="10" font-weight="600">组织管理</text>
            </g>
            <g transform="translate(215, 318)">
              <rect x="-42" y="-14" width="84" height="28" rx="14" fill="#D1FAE5" stroke="#10B981" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#065F46" font-size="10" font-weight="600">技术方案设计</text>
            </g>
            <g transform="translate(578, 318)">
              <rect x="-42" y="-14" width="84" height="28" rx="14" fill="#D1FAE5" stroke="#10B981" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#065F46" font-size="10" font-weight="600">组织架构升级</text>
            </g>
            <g transform="translate(295, 370)">
              <rect x="-42" y="-14" width="84" height="28" rx="14" fill="#D1FAE5" stroke="#10B981" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#065F46" font-size="10" font-weight="600">数据治理体系</text>
            </g>
            <g transform="translate(498, 372)">
              <rect x="-48" y="-14" width="96" height="28" rx="14" fill="#D1FAE5" stroke="#10B981" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#065F46" font-size="10" font-weight="600">业务流程优化</text>
            </g>

            <!-- 标签（紫） -->
            <g transform="translate(158, 95)">
              <rect x="-32" y="-12" width="64" height="24" rx="12" fill="#F3E8FF" stroke="#8B5CF6" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#6B21A8" font-size="10" font-weight="600">技术采购</text>
            </g>
            <g transform="translate(620, 88)">
              <rect x="-32" y="-12" width="64" height="24" rx="12" fill="#F3E8FF" stroke="#8B5CF6" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#6B21A8" font-size="10" font-weight="600">系统集成</text>
            </g>
            <g transform="translate(168, 348)">
              <rect x="-32" y="-12" width="64" height="24" rx="12" fill="#F3E8FF" stroke="#8B5CF6" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#6B21A8" font-size="10" font-weight="600">数据管理</text>
            </g>
            <g transform="translate(615, 348)">
              <rect x="-32" y="-12" width="64" height="24" rx="12" fill="#F3E8FF" stroke="#8B5CF6" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#6B21A8" font-size="10" font-weight="600">流程管理</text>
            </g>
            <g transform="translate(250, 420)">
              <rect x="-32" y="-12" width="64" height="24" rx="12" fill="#F3E8FF" stroke="#8B5CF6" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#6B21A8" font-size="10" font-weight="600">数据安全</text>
            </g>
            <g transform="translate(538, 422)">
              <rect x="-32" y="-12" width="64" height="24" rx="12" fill="#F3E8FF" stroke="#8B5CF6" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#6B21A8" font-size="10" font-weight="600">效率提升</text>
            </g>
            <g transform="translate(390, 425)">
              <rect x="-32" y="-12" width="64" height="24" rx="12" fill="#F3E8FF" stroke="#8B5CF6" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#6B21A8" font-size="10" font-weight="600">战略规划</text>
            </g>
            <g transform="translate(395, 370)">
              <rect x="-36" y="-12" width="72" height="24" rx="12" fill="#FEF3C7" stroke="#F59E0B" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#92400E" font-size="10" font-weight="600">数字化转型</text>
            </g>
            <g transform="translate(395, 420)">
              <rect x="-32" y="-12" width="64" height="24" rx="12" fill="#F3E8FF" stroke="#8B5CF6" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#6B21A8" font-size="10" font-weight="600">业务创新</text>
            </g>
            <g transform="translate(322, 423)">
              <rect x="-32" y="-12" width="64" height="24" rx="12" fill="#F3E8FF" stroke="#8B5CF6" stroke-width="1.2" />
              <text y="4" text-anchor="middle" fill="#6B21A8" font-size="10" font-weight="600">降本增效</text>
            </g>
          </g>
        </svg>

        <!-- 底部控制 + 图例 -->
        <div class="canvas-footer">
          <div class="zoom-controls">
            <button class="zc-btn"><Icon name="expand" :size="14" /></button>
            <button class="zc-btn"><Icon name="minus" :size="14" /></button>
            <span class="zoom-level">100%</span>
            <button class="zc-btn"><Icon name="plus" :size="14" /></button>
            <button class="zc-btn"><Icon name="gridview" :size="14" /></button>
          </div>
          <div class="legend">
            <span class="leg-item"><i class="leg-dot" style="background:#3B82F6"></i> 文档</span>
            <span class="leg-item"><i class="leg-dot" style="background:#10B981"></i> 知识点</span>
            <span class="leg-item"><i class="leg-dot" style="background:#8B5CF6"></i> 标签</span>
            <span class="leg-item"><i class="leg-dot" style="background:#F59E0B"></i> 业务分类</span>
            <span class="leg-divider"></span>
            <span class="leg-line leg-dashed"></span> 关联
            <span class="leg-line leg-arrow"></span> 引用
            <span class="leg-line leg-solid"></span> 包含
          </div>
        </div>
        <p class="canvas-hint">拖拽节点可移动，滚轮缩放画布</p>
      </div>

      <!-- 右：数据面板 -->
      <aside class="stats-panel card">
        <div class="panel-head">
          <span class="panel-title">图谱数据统计</span>
          <Icon name="alert" :size="14" class="info-hint" />
        </div>

        <!-- 统计数字网格 -->
        <div class="stat-grid">
          <div v-for="(s, i) in stats" :key="i" class="stat-cell">
            <div class="sc-icon-wrap" :style="{ background: s.color + '14' }">
              <Icon :name="s.icon" :size="18" :style="{ color: s.color }" />
            </div>
            <div class="sc-info">
              <div class="sc-label">{{ s.label }}</div>
              <div class="sc-value" :style="{ color: s.color }">{{ s.value }}</div>
            </div>
          </div>
        </div>

        <!-- 热门节点 -->
        <div class="section-block">
          <div class="section-title">热门节点 Top 5</div>
          <div class="hot-list">
            <div v-for="(n, i) in hotNodes" :key="i" class="hot-item">
              <span class="hot-rank" :class="{ top3: i < 3 }">{{ i + 1 }}</span>
              <span class="hot-dot" :style="{ background: n.color }"></span>
              <span class="hot-name">{{ n.name }}</span>
              <span class="hot-count">关联数：<strong>{{ n.count }}</strong></span>
            </div>
          </div>
        </div>

        <!-- 最近新增 -->
        <div class="section-block">
          <div class="section-header">
            <span class="section-title">最近新增的节点</span>
            <a href="#" class="more-link">更多 &gt;</a>
          </div>
          <div class="recent-list">
            <div v-for="(n, i) in recentNodes" :key="i" class="recent-item">
              <span class="recent-icon" :style="{ background: n.color + '18', color: n.color }">
                <Icon :name="n.type === 'pdf' ? 'pdf' : n.type === 'excel' ? 'excel' : n.type === 'pptx' ? 'pptx' : 'doc'" :size="13" />
              </span>
              <span class="recent-name">{{ n.name }}</span>
              <span class="recent-time">{{ n.time }}</span>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.graph-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.page-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

/* ---- 工具栏 ---- */
.graph-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  gap: 12px;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.g-search {
  position: relative;
  width: 240px;
}
.g-input {
  width: 100%;
  height: 34px;
  padding: 0 34px 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
}
.g-input:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); }
.g-search-icon {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-tertiary);
  pointer-events: none;
}

.g-filter {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  white-space: nowrap;
  background: var(--bg-surface);
}
.g-filter span { color: var(--text-primary); font-weight: 500; }
.g-filter:hover { border-color: var(--brand); }

.g-date {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  background: var(--bg-surface);
}
.date-ph { color: var(--text-placeholder); margin-left: 8px; }

.g-reset { white-space: nowrap; }

/* ---- 图布主体行 ---- */
.graph-body {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 14px;
  min-height: 520px;
}

.canvas-area {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}
.force-graph {
  width: 100%;
  flex: 1;
  min-height: 420px;
  cursor: grab;
  background:
    radial-gradient(circle at 30% 40%, rgba(1, 77, 178, 0.03) 0%, transparent 50%),
    radial-gradient(circle at 70% 60%, rgba(16, 185, 129, 0.02) 0%, transparent 50%);
}
.force-graph:active { cursor: grabbing; }
.edge-label { font-size: 10px; font-weight: 500; pointer-events: none; }

/* 画布底部 */
.canvas-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-surface);
}
.zoom-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}
.zc-btn {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
}
.zc-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.zoom-level {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  min-width: 40px;
  text-align: center;
}

.legend {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 11px;
  color: var(--text-secondary);
  flex-wrap: wrap;
}
.leg-item { display: flex; align-items: center; gap: 4px; }
.leg-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  display: inline-block;
}
.leg-divider { width: 1px; height: 14px; background: var(--border); }
.leg-line {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.leg-line::before {
  content: '';
  display: inline-block;
  width: 20px;
  height: 0;
  border-top: 1.5px solid #94A3B8;
}
.leg-dashed::before { border-top-style: dashed; }
.leg-arrow::before {
  width: 20px;
  border-top: 1.5px solid #94A3B8;
  position: relative;
}
.leg-arrow::after {
  content: '';
  position: absolute;
  right: -1px;
  top: -4px;
  border: 4px solid transparent;
  border-left: 4px solid #94A3B8;
}
.leg-solid::before { border-top-style: solid; border-color: #CBD5E1; }

.canvas-hint {
  text-align: center;
  font-size: 11px;
  color: var(--text-placeholder);
  padding: 6px;
  margin: 0;
}

/* ---- 右侧统计面板 ---- */
.stats-panel {
  padding: 16px;
  overflow-y: auto;
}
.panel-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 14px;
}
.panel-title { font-size: 15px; font-weight: 700; }
.info-hint { color: var(--text-tertiary); cursor: pointer; }

.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 18px;
}
.stat-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: var(--radius-md);
  background: var(--bg-subtle);
}
.sc-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.sc-label { font-size: 11px; color: var(--text-tertiary); }
.sc-value { font-size: 17px; font-weight: 800; letter-spacing: -0.01em; line-height: 1.2; }

.section-block { margin-bottom: 18px; }
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.section-title { font-size: 13px; font-weight: 700; color: var(--text-primary); }
.more-link { font-size: 12px; color: var(--brand); text-decoration: none; }
.more-link:hover { text-decoration: underline; }

.hot-list { display: flex; flex-direction: column; gap: 6px; }
.hot-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  transition: background var(--dur-fast);
}
.hot-item:hover { background: var(--bg-hover); }
.hot-rank {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  background: var(--bg-subtle);
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.hot-rank.top3 { background: var(--brand-soft); color: var(--brand); }
.hot-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.hot-name {
  font-size: 12.5px;
  color: var(--text-primary);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hot-count {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
}
.hot-count strong { color: var(--text-secondary); }

.recent-list { display: flex; flex-direction: column; gap: 6px; }
.recent-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: var(--radius-sm);
  transition: background var(--dur-fast);
}
.recent-item:hover { background: var(--bg-hover); }
.recent-icon {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.recent-name {
  font-size: 12px;
  color: var(--text-primary);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.recent-time { font-size: 11px; color: var(--text-tertiary); white-space: nowrap; }

</style>
