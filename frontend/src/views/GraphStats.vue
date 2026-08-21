<script setup lang="ts">
// 知识图谱 — 图谱统计视图（实体/关系/知识库概览 + 类型分布 + 热门/最近 + 知识缺口）。
import { onMounted } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { useGraphData } from '@/composables/useGraphData'
import '@/assets/graph.css'
import '@/assets/dashboard.css'

const {
  stats, typeBars, hotNodes, recentNodes, nodeColor,
  gapSignals, loadGaps, dismissGap, avgDegree, kbName,
  rebuildProgress,
} = useGraphData()

onMounted(() => { void loadGaps(true) })
</script>

<template>
  <div class="graph-page">
    <!-- 图谱重建进度横幅 -->
    <div v-if="rebuildProgress" class="rebuild-banner" :class="`rb-${rebuildProgress.status}`">
      <span v-if="rebuildProgress.status === 'running'" class="rb-spinner" />
      <Icon v-else :name="rebuildProgress.status === 'done' ? 'check' : 'alert'" :size="16" class="rb-icon" />
      <span v-if="rebuildProgress.status === 'running'" class="rb-text">
        正在重建「{{ rebuildProgress.kbName }}」图谱… 已处理 {{ rebuildProgress.processed }}/{{ rebuildProgress.total }} 篇
      </span>
      <span v-else-if="rebuildProgress.status === 'done'" class="rb-text">「{{ rebuildProgress.kbName }}」图谱重建完成</span>
      <span v-else class="rb-text">「{{ rebuildProgress.kbName }}」图谱重建异常，请重试</span>
      <span v-if="rebuildProgress.status === 'running' && rebuildProgress.total" class="rb-track"
        ><i class="rb-fill" :style="{ width: Math.round(rebuildProgress.processed / rebuildProgress.total * 100) + '%' }" /></span>
    </div>
    <div class="stats-page">
      <div class="stats-row">
        <div class="stat-card card" style="--card-accent: var(--accent-blue)">
          <div class="sc-icon"><Icon name="graph" :size="18"/></div>
          <div class="sc-body"><div class="sc-label">实体节点</div><div class="sc-value">{{ stats?.nodeCount ?? 0 }}</div></div>
        </div>
        <div class="stat-card card" style="--card-accent: var(--accent-green)">
          <div class="sc-icon"><Icon name="link" :size="18"/></div>
          <div class="sc-body"><div class="sc-label">关系边</div><div class="sc-value">{{ stats?.edgeCount ?? 0 }}</div></div>
        </div>
        <div class="stat-card card" style="--card-accent: var(--accent-rose)">
          <div class="sc-icon"><Icon name="alert" :size="18"/></div>
          <div class="sc-body"><div class="sc-label">知识缺口</div><div class="sc-value">{{ gapSignals.length }}</div></div>
        </div>
        <div class="stat-card card" style="--card-accent: var(--accent-amber)">
          <div class="sc-icon"><Icon name="tag" :size="18"/></div>
          <div class="sc-body"><div class="sc-label">实体类型</div><div class="sc-value">{{ Object.keys(stats?.typeCounts || {}).length }}</div></div>
        </div>
        <div class="stat-card card" style="--card-accent: var(--accent-blue)">
          <div class="sc-icon"><Icon name="crosshair" :size="18"/></div>
          <div class="sc-body"><div class="sc-label">平均度数</div><div class="sc-value">{{ avgDegree }}</div></div>
        </div>
      </div>

      <div class="card stat-block">
        <div class="section-title">实体类型分布</div>
        <div v-if="typeBars.length" class="type-bars">
          <div v-for="(t, i) in typeBars" :key="i" class="type-bar">
            <span class="tb-label">{{ t.label }}</span>
            <span class="tb-track"><i class="tb-fill" :style="{ width: t.pct + '%' }"></i></span>
            <span class="tb-count">{{ t.count }}</span>
          </div>
        </div>
        <EmptyState v-else />
      </div>

      <div class="grid-2">
        <div class="card stat-block">
          <div class="section-title">热门知识点 Top 5</div>
          <div v-if="hotNodes.length" class="hot-list">
            <div v-for="(item, i) in hotNodes" :key="item.id" class="hot-item">
              <span class="hot-rank" :class="{ top3: i < 3 }">{{ i + 1 }}</span>
              <span class="hot-dot" :style="{ background: nodeColor(item.kbId) }"></span>
              <span class="hot-name">{{ item.label }}</span>
              <span class="hot-count">度数 <strong>{{ item.degree }}</strong></span>
            </div>
          </div>
          <EmptyState v-else />
        </div>
        <div class="card stat-block">
          <div class="section-title">最近新增的实体</div>
          <div v-if="recentNodes.length" class="recent-list">
            <div v-for="n in recentNodes" :key="n.id" class="recent-item">
              <span class="recent-icon" :style="{ background: nodeColor(n.kbId) + '18', color: nodeColor(n.kbId) }">
                <Icon name="graph" :size="13" />
              </span>
              <span class="recent-name">{{ n.label }}</span>
              <span class="recent-time">{{ (n.createdAt || '').slice(5, 10) }}</span>
            </div>
          </div>
          <EmptyState v-else />
        </div>
      </div>

      <!-- 知识缺口信号（全部知识库汇总） -->
      <div class="card stat-block">
        <div class="section-title">知识缺口（图谱未命中问题 · 全部知识库）</div>
        <div v-if="gapSignals.length" class="gap-list">
          <div v-for="(g, i) in gapSignals" :key="i" class="gap-item">
            <span class="gap-kb">{{ kbName(g.kbId) }}</span>
            <span class="gap-q">{{ g.question }}</span>
            <span class="gap-count">×{{ g.count }}</span>
            <button class="btn btn-ghost btn-sm gap-dismiss" title="标记已处理" @click="dismissGap(g.kbId, g.question)">
              <Icon name="check" :size="13" />
            </button>
          </div>
        </div>
        <EmptyState v-else />
      </div>
    </div>
  </div>
</template>

<style scoped>
.gap-list { display: flex; flex-direction: column; gap: 8px; }
.gap-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px; border-radius: var(--radius-md);
  background: var(--bg-secondary, #f8fafc);
}
.gap-kb {
  flex-shrink: 0; font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: var(--accent-blue-soft); color: var(--accent-blue); white-space: nowrap;
}
.gap-q { flex: 1; font-size: 13px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gap-count { font-size: 12px; color: var(--accent-amber); font-weight: 600; white-space: nowrap; }
.gap-dismiss { padding: 2px 6px; opacity: .6; transition: opacity .15s; }
.gap-dismiss:hover { opacity: 1; color: var(--accent-green); }
</style>