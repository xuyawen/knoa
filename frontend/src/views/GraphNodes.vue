<script setup lang="ts">
// 知识图谱 — 节点管理视图（实体表格 + 分页）。
import Icon from '@/components/ui/Icon.vue'
import DataTable from '@/components/ui/DataTable.vue'
import Pagination from '@/components/ui/Pagination.vue'
import { useGraphData } from '@/composables/useGraphData'
import '@/assets/graph.css'

const {
  graph, nodeColumns, pagedNodes, selectedId, degree, kbName,
  nodePage, nodePageSize,
} = useGraphData()
</script>

<template>
  <div class="graph-page">
    <div class="card node-card">
      <div class="panel-head">
        <span class="panel-title">实体节点（{{ graph?.nodes.length || 0 }}）</span>
        <Icon name="node" :size="14" class="info-hint" />
      </div>
      <div class="node-scroll">
        <DataTable
          :columns="nodeColumns"
          :rows="pagedNodes"
          row-key="id"
          clickable
          @row-click="(n) => (selectedId = n.id)"
        >
          <template #cell="{ row, col }">
            <template v-if="col.key === 'label'">{{ row.label }}</template>
            <template v-else-if="col.key === 'type'">{{ row.type || '—' }}</template>
            <template v-else-if="col.key === 'kb'">{{ kbName(row.kbId) }}</template>
            <template v-else-if="col.key === 'degree'">{{ degree[row.id] || 0 }}</template>
          </template>
          <template #empty>暂无实体节点</template>
        </DataTable>
      </div>
      <Pagination
        v-if="(graph?.nodes.length || 0) > 0"
        v-model:page="nodePage"
        v-model:page-size="nodePageSize"
        :total="graph?.nodes.length || 0"
        :page-sizes="[10, 15, 30]"
      />
    </div>
  </div>
</template>
