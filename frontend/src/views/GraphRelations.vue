<script setup lang="ts">
// 知识图谱 — 关系检索视图（服务端分页/搜索，解耦画布采样；删除需二次确认）。
import { onMounted, ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Pagination from '@/components/ui/Pagination.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import { useGraphData } from '@/composables/useGraphData'
import '@/assets/graph.css'

const { relTerm, pagedEdges, relPage, relPageSize, edgeTotal, edgeListLoading, fetchEdgeList, removeEdge } = useGraphData()

onMounted(() => { void fetchEdgeList() })

// 删除确认：先记下待删边，弹窗确认后才真删（危险操作二次确认，防误触）
const pendingDelete = ref<{ id: string; desc: string } | null>(null)
function askDelete(e: { id: string; sourceLabel: string; relation: string; targetLabel: string }) {
  pendingDelete.value = { id: e.id, desc: `${e.sourceLabel} —${e.relation}→ ${e.targetLabel}` }
}
async function confirmDelete() {
  if (!pendingDelete.value) return
  await removeEdge(pendingDelete.value.id)
  pendingDelete.value = null
}
</script>

<template>
  <div class="graph-page">
    <div class="card rel-card">
      <div class="panel-head">
        <span class="panel-title">关系检索（{{ edgeTotal }}）</span>
      </div>
      <div class="g-search" style="margin-bottom: 14px">
        <input v-model="relTerm" type="text" placeholder="搜索关系名称 / 实体…" class="g-input" />
        <Icon name="search" :size="15" class="g-search-icon" />
      </div>
      <div class="rel-list">
        <div v-for="e in pagedEdges" :key="e.id" class="rel-item">
          <span class="rel-src">{{ e.sourceLabel }}</span>
          <span class="rel-arrow">{{ e.relation }}</span>
          <span class="rel-tgt">{{ e.targetLabel }}</span>
          <button class="btn btn-ghost btn-sm rel-del" title="删除关系" @click="askDelete(e)">
            <Icon name="trash" :size="13" />
          </button>
        </div>
        <div v-if="!edgeTotal && !edgeListLoading" class="empty-hint">暂无匹配的关系</div>
      </div>
      <Pagination
        v-if="edgeTotal > 0"
        v-model:page="relPage"
        v-model:page-size="relPageSize"
        :total="edgeTotal"
        :page-sizes="[10, 15, 30]"
      />
    </div>
    <ConfirmDialog
      :show="!!pendingDelete"
      title="删除关系"
      :message="`确定删除关系「${pendingDelete?.desc}」吗？此操作不可恢复。`"
      confirm-text="删除"
      danger
      @close="pendingDelete = null"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
.rel-item { display: flex; align-items: center; }
.rel-del { margin-left: auto; padding: 2px 6px; color: var(--accent-red, #ef4444); opacity: .6; transition: opacity .15s; }
.rel-del:hover { opacity: 1 !important; }
</style>
