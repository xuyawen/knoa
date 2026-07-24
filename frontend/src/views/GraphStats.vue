<script setup lang="ts">
// 知识图谱 — 图谱统计视图（实体/关系/知识库概览 + 类型分布 + 热门/最近）。
import Icon from '@/components/ui/Icon.vue'
import { useGraphData } from '@/composables/useGraphData'
import '@/assets/graph.css'

const {
  stats, typeBars, hotNodes, recentNodes, nodeColor, selectedId,
} = useGraphData()
</script>

<template>
  <div class="graph-page">
    <div class="stats-page">
      <div class="stat-grid wide">
        <div class="stat-cell">
          <div class="sc-icon-wrap" style="background:var(--accent-blue-soft)"><Icon name="graph" :size="18" style="color:var(--accent-blue)" /></div>
          <div class="sc-info"><div class="sc-label">实体节点</div><div class="sc-value" style="color:var(--accent-blue)">{{ stats?.nodeCount ?? 0 }}</div></div>
        </div>
        <div class="stat-cell">
          <div class="sc-icon-wrap" style="background:var(--accent-green-soft)"><Icon name="link" :size="18" style="color:var(--accent-green)" /></div>
          <div class="sc-info"><div class="sc-label">关系边</div><div class="sc-value" style="color:var(--accent-green)">{{ stats?.edgeCount ?? 0 }}</div></div>
        </div>
        <div class="stat-cell">
          <div class="sc-icon-wrap" style="background:var(--accent-violet-soft)"><Icon name="folder" :size="18" style="color:var(--accent-violet)" /></div>
          <div class="sc-info"><div class="sc-label">覆盖知识库</div><div class="sc-value" style="color:var(--accent-violet)">{{ stats?.kbCount ?? 0 }}</div></div>
        </div>
        <div class="stat-cell">
          <div class="sc-icon-wrap" style="background:var(--accent-amber-soft)"><Icon name="tag" :size="18" style="color:var(--accent-amber)" /></div>
          <div class="sc-info"><div class="sc-label">实体类型</div><div class="sc-value" style="color:var(--accent-amber)">{{ Object.keys(stats?.typeCounts || {}).length }}</div></div>
        </div>
      </div>

      <div class="card stat-block">
        <div class="section-title">实体类型分布</div>
        <div class="type-bars">
          <div v-for="(t, i) in typeBars" :key="i" class="type-bar">
            <span class="tb-label">{{ t.label }}</span>
            <span class="tb-track"><i class="tb-fill" :style="{ width: t.pct + '%' }"></i></span>
            <span class="tb-count">{{ t.count }}</span>
          </div>
        </div>
      </div>

      <div class="grid-2">
        <div class="card stat-block">
          <div class="section-title">热门知识点 Top 5</div>
          <div class="hot-list">
            <div v-for="(item, i) in hotNodes" :key="item.id" class="hot-item" @click="selectedId = item.id">
              <span class="hot-rank" :class="{ top3: i < 3 }">{{ i + 1 }}</span>
              <span class="hot-dot" :style="{ background: nodeColor(item.kbId) }"></span>
              <span class="hot-name">{{ item.label }}</span>
              <span class="hot-count">度数 <strong>{{ item.degree }}</strong></span>
            </div>
          </div>
        </div>
        <div class="card stat-block">
          <div class="section-title">最近新增的实体</div>
          <div class="recent-list">
            <div v-for="n in recentNodes" :key="n.id" class="recent-item" @click="selectedId = n.id">
              <span class="recent-icon" :style="{ background: nodeColor(n.kbId) + '18', color: nodeColor(n.kbId) }">
                <Icon name="graph" :size="13" />
              </span>
              <span class="recent-name">{{ n.label }}</span>
              <span class="recent-time">{{ (n.createdAt || '').slice(5, 10) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
