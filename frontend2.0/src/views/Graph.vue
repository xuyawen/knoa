<script setup lang="ts">
// 知识图谱（对应截图 #6）：SVG 图布 + 统计面板 + 左侧导航 + 筛选。
// 界面壳阶段：节点/边为静态示例，未接后端图谱数据。
import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'

const nav = [
  { key: 'global', label: '全局图谱' },
  { key: 'nodes', label: '节点管理' },
  { key: 'rel', label: '关系检索' },
  { key: 'stat', label: '图谱统计' },
]
const activeNav = ref('global')

// 静态示例节点（坐标基于 760x440 viewBox）
const nodes = [
  { id: 1, x: 380, y: 210, label: '数据安全', type: 'category', r: 26 },
  { id: 2, x: 200, y: 120, label: '安全管理制度', type: 'doc', r: 18 },
  { id: 3, x: 560, y: 130, label: '访问控制', type: 'knowledge', r: 16 },
  { id: 4, x: 200, y: 310, label: '合规', type: 'tag', r: 14 },
  { id: 5, x: 560, y: 310, label: '数据分级', type: 'knowledge', r: 16 },
  { id: 6, x: 380, y: 60, label: '培训资料', type: 'doc', r: 18 },
  { id: 7, x: 380, y: 370, label: '审计', type: 'tag', r: 14 },
]
const edges = [
  [2, 1], [6, 1], [3, 1], [5, 1], [4, 1], [7, 1], [3, 5],
]
const typeColor: Record<string, string> = {
  doc: 'var(--node-doc)',
  knowledge: 'var(--node-knowledge)',
  tag: 'var(--node-tag)',
  category: 'var(--node-category)',
}
const typeLabel: Record<string, string> = {
  doc: '文档', knowledge: '知识点', tag: '标签', category: '业务分类',
}

const stats = [
  { label: '节点数', value: '1,245' },
  { label: '关系数', value: '3,672' },
  { label: '文档节点', value: '486' },
  { label: '知识点', value: '612' },
]
const topNodes = ['数据安全', '访问控制', '数据分级', '合规审计', '培训体系']
</script>

<template>
  <div class="page graph fade-up">
    <header class="page-head">
      <div class="flex items-center">
        <h1 class="page-title">知识图谱</h1>
        <span class="todo-flag"><Icon name="sparkles" :size="12" />界面壳 · 示例数据</span>
      </div>
      <p class="page-sub">以图结构呈现知识关联，支撑多跳推理与知识发现</p>
    </header>

    <div class="graph-body">
      <!-- 左侧导航 -->
      <aside class="graph-nav card">
        <div v-for="n in nav" :key="n.key" class="nav-item" :class="{ active: activeNav === n.key }" @click="activeNav = n.key">
          <Icon :name="n.key === 'rel' ? 'search' : n.key === 'stat' ? 'dashboard' : 'graph'" :size="18" />
          <span>{{ n.label }}</span>
        </div>
        <div class="divider" style="margin: 8px 0" />
        <div class="filter-block">
          <div class="filter-label">节点类型</div>
          <span v-for="(c, k) in typeColor" :key="k" class="lg-chip">
            <span class="dot" :style="{ background: c }" />{{ typeLabel[k] }}
          </span>
        </div>
      </aside>

      <!-- 图布 -->
      <section class="graph-canvas card">
        <div class="canvas-head">
          <span class="text-secondary text-sm">全局知识图谱（示例布局）</span>
          <div class="canvas-ctrl">
            <button class="icon-btn"><Icon name="refresh" :size="16" /></button>
            <button class="icon-btn"><Icon name="eye" :size="16" /></button>
            <button class="icon-btn"><Icon name="more" :size="16" /></button>
          </div>
        </div>
        <svg class="canvas" viewBox="0 0 760 440">
          <line
            v-for="(e, i) in edges"
            :key="`e${i}`"
            :x1="nodes[e[0] - 1].x" :y1="nodes[e[0] - 1].y"
            :x2="nodes[e[1] - 1].x" :y2="nodes[e[1] - 1].y"
            stroke="var(--border-strong)" stroke-width="1.5"
          />
          <g v-for="nd in nodes" :key="nd.id">
            <circle :cx="nd.x" :cy="nd.y" :r="nd.r" :fill="typeColor[nd.type]" fill-opacity="0.16" :stroke="typeColor[nd.type]" stroke-width="2" />
            <text :x="nd.x" :y="nd.y + 4" text-anchor="middle" font-size="11" font-weight="600" :fill="typeColor[nd.type]">{{ nd.label }}</text>
          </g>
        </svg>
      </section>

      <!-- 右侧统计 -->
      <aside class="graph-stat card">
        <h3 class="stat-h">图谱统计</h3>
        <div class="stat-grid2">
          <div v-for="s in stats" :key="s.label" class="stat-cell">
            <div class="stat-v">{{ s.value }}</div>
            <div class="stat-l">{{ s.label }}</div>
          </div>
        </div>
        <div class="divider" />
        <div class="hot-h">热门节点 · Top 5</div>
        <ul class="hot-list">
          <li v-for="(h, i) in topNodes" :key="i">
            <span class="rank">{{ i + 1 }}</span>
            <span class="hot-name">{{ h }}</span>
          </li>
        </ul>
        <button class="btn btn-ghost btn-sm export">导出图谱</button>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.graph-body {
  display: grid;
  grid-template-columns: 210px 1fr 240px;
  gap: 16px;
  align-items: start;
}
.graph-nav { padding: 12px; }
.graph-nav .nav-item { margin-bottom: 2px; }
.filter-block { padding: 8px 10px 0; }
.filter-label { font-size: 11px; color: var(--text-tertiary); margin-bottom: 8px; }
.lg-chip { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--text-secondary); margin: 0 12px 8px 0; }
.dot { width: 9px; height: 9px; border-radius: 3px; }

.graph-canvas { padding: 0; overflow: hidden; }
.canvas-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--border);
}
.canvas-ctrl { display: flex; gap: 2px; }
.canvas { width: 100%; height: 460px; display: block; background:
  radial-gradient(circle at 50% 45%, var(--bg-surface-2), var(--bg-surface)); }

.graph-stat { padding: 18px; }
.stat-h { margin: 0 0 14px; font-size: 15px; font-weight: 600; }
.stat-grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.stat-cell {
  padding: 12px;
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  text-align: center;
}
.stat-v { font-size: 19px; font-weight: 700; color: var(--brand); }
.stat-l { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }

.hot-h { font-size: 13px; font-weight: 600; margin: 16px 0 10px; }
.hot-list { list-style: none; padding: 0; margin: 0 0 14px; display: flex; flex-direction: column; gap: 8px; }
.hot-list li { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.rank {
  width: 20px; height: 20px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--brand-soft); color: var(--brand); font-size: 11px; font-weight: 700;
}
.export { width: 100%; }

@media (max-width: 1080px) {
  .graph-body { grid-template-columns: 1fr; }
  .graph-nav, .graph-stat { order: 2; }
}
</style>
