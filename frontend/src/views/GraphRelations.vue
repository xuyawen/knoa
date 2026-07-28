<script setup lang="ts">
// 知识图谱 — 关系检索视图（按关键词过滤实体关系，前端分页，支持删除）。
import Icon from '@/components/ui/Icon.vue'
import Pagination from '@/components/ui/Pagination.vue'
import { useGraphData } from '@/composables/useGraphData'
import '@/assets/graph.css'

const { relTerm, filteredEdges, pagedEdges, relPage, relPageSize, nodeLabel, removeEdge } = useGraphData()
</script>

<template>
  <div class="graph-page">
    <div class="card rel-card">
      <div class="panel-head">
        <span class="panel-title">关系检索（{{ filteredEdges.length }}）</span>
      </div>
      <div class="g-search" style="margin-bottom: 14px">
        <input v-model="relTerm" type="text" placeholder="搜索关系名称 / 实体…" class="g-input" />
        <Icon name="search" :size="15" class="g-search-icon" />
      </div>
      <div class="rel-list">
        <div v-for="(e, i) in pagedEdges" :key="i" class="rel-item">
          <span class="rel-src">{{ nodeLabel(e.source) }}</span>
          <span class="rel-arrow">{{ e.relation }}</span>
          <span class="rel-tgt">{{ nodeLabel(e.target) }}</span>
          <button v-if="e.id" class="btn btn-ghost btn-sm rel-del" title="删除关系" @click="removeEdge(e.id!)">
            <Icon name="trash" :size="13" />
          </button>
        </div>
        <div v-if="!filteredEdges.length" class="empty-hint">暂无匹配的关系</div>
      </div>
      <Pagination
        v-if="filteredEdges.length > 0"
        v-model:page="relPage"
        v-model:page-size="relPageSize"
        :total="filteredEdges.length"
        :page-sizes="[10, 15, 30]"
      />
    </div>
  </div>
</template>

<style scoped>
.rel-item { display: flex; align-items: center; }
.rel-del { margin-left: auto; padding: 2px 6px; color: var(--accent-red, #ef4444); opacity: .6; transition: opacity .15s; }
.rel-del:hover { opacity: 1 !important; }
</style>
