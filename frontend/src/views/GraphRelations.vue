<script setup lang="ts">
// 知识图谱 — 关系检索视图（按关键词过滤实体关系）。
import Icon from '@/components/ui/Icon.vue'
import { useGraphData } from '@/composables/useGraphData'
import '@/assets/graph.css'

const { relTerm, filteredEdges, nodeLabel } = useGraphData()
</script>

<template>
  <div class="graph-page">
    <div class="card rel-card">
      <div class="panel-head">
        <span class="panel-title">关系检索</span>
        <Icon name="link" :size="14" class="info-hint" />
      </div>
      <div class="g-search" style="margin-bottom: 14px">
        <input v-model="relTerm" type="text" placeholder="搜索关系名称 / 实体…" class="g-input" />
        <Icon name="search" :size="15" class="g-search-icon" />
      </div>
      <div class="rel-list">
        <div v-for="(e, i) in filteredEdges" :key="i" class="rel-item">
          <span class="rel-src">{{ nodeLabel(e.source) }}</span>
          <span class="rel-arrow">{{ e.relation }}</span>
          <span class="rel-tgt">{{ nodeLabel(e.target) }}</span>
        </div>
        <div v-if="!filteredEdges.length" class="empty-hint">暂无匹配的关系</div>
      </div>
    </div>
  </div>
</template>
