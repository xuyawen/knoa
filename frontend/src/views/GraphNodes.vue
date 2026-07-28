<script setup lang="ts">
// 知识图谱 — 节点管理视图（实体表格 + 分页 + 多选合并）。
import { ref, computed } from 'vue'
import Pagination from '@/components/ui/Pagination.vue'
import Icon from '@/components/ui/Icon.vue'
import { useGraphData } from '@/composables/useGraphData'
import '@/assets/graph.css'

const {
  graph, pagedNodes, degree, kbName,
  nodePage, nodePageSize, mergeNodes,
} = useGraphData()

/* ---- 多选 + 合并 ---- */
const selectedIds = ref<Set<string>>(new Set())
const mergeDialogVisible = ref(false)
const mergeLabel = ref('')
const mergeType = ref('')

function toggleSelect(id: string) {
  const s = new Set(selectedIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selectedIds.value = s
}
const allPageSelected = computed(() =>
  pagedNodes.value.length > 0 && pagedNodes.value.every(n => selectedIds.value.has(n.id)),
)
function toggleSelectAll() {
  const s = new Set(selectedIds.value)
  if (allPageSelected.value) {
    pagedNodes.value.forEach(n => s.delete(n.id))
  } else {
    pagedNodes.value.forEach(n => s.add(n.id))
  }
  selectedIds.value = s
}
function openMerge() {
  mergeLabel.value = ''
  mergeType.value = ''
  mergeDialogVisible.value = true
}
async function confirmMerge() {
  if (!mergeLabel.value.trim()) return
  await mergeNodes([...selectedIds.value], mergeLabel.value.trim(), mergeType.value.trim() || undefined)
  mergeDialogVisible.value = false
  selectedIds.value = new Set()
}
</script>

<template>
  <div class="graph-page">
    <div class="card node-card">
      <div class="panel-head">
        <span class="panel-title">实体节点（{{ graph?.nodes.length || 0 }}）</span>
        <button class="btn btn-sm" :class="selectedIds.size >= 2 ? 'btn-primary' : 'btn-ghost'" :disabled="selectedIds.size < 2" @click="openMerge">
          <Icon name="layers" :size="13" /> 合并{{ selectedIds.size >= 2 ? `（${selectedIds.size}）` : '' }}
        </button>
      </div>
      <div class="node-scroll">
        <table class="node-table">
          <thead>
            <tr>
              <th class="col-check"><input type="checkbox" :checked="allPageSelected" @change="toggleSelectAll" /></th>
              <th>实体</th><th>类型</th><th>知识库</th><th>度数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in pagedNodes" :key="row.id" :class="{ selected: selectedIds.has(row.id) }">
              <td class="col-check"><input type="checkbox" :checked="selectedIds.has(row.id)" @change="toggleSelect(row.id)" /></td>
              <td class="td-label">{{ row.label }}</td>
              <td>{{ row.type || '—' }}</td>
              <td>{{ kbName(row.kbId) }}</td>
              <td>{{ degree[row.id] || 0 }}</td>
            </tr>
            <tr v-if="!pagedNodes.length"><td colspan="5" class="empty-cell">暂无实体节点</td></tr>
          </tbody>
        </table>
      </div>
      <Pagination
        v-if="(graph?.nodes.length || 0) > 0"
        v-model:page="nodePage"
        v-model:page-size="nodePageSize"
        :total="graph?.nodes.length || 0"
        :page-sizes="[10, 15, 30]"
      />
    </div>

    <!-- 合并弹窗 -->
    <Teleport to="body">
      <div v-if="mergeDialogVisible" class="modal-mask" @click.self="mergeDialogVisible = false">
        <div class="modal-box">
          <div class="modal-title">合并实体</div>
          <p class="modal-desc">将已选的 {{ selectedIds.size }} 个实体合并为一个新节点，所有关联边将重定向。</p>
          <label class="modal-label">目标名称</label>
          <input v-model="mergeLabel" class="g-input modal-input" placeholder="合并后的实体名称" />
          <label class="modal-label">类型（可选）</label>
          <input v-model="mergeType" class="g-input modal-input" placeholder="如：流程 / 概念 / 产品" />
          <div class="modal-actions">
            <button class="btn btn-ghost btn-sm" @click="mergeDialogVisible = false">取消</button>
            <button class="btn btn-primary btn-sm" :disabled="!mergeLabel.trim()" @click="confirmMerge">确认合并</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.node-card { padding: 20px; }
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.panel-title { font-size: 15px; font-weight: 700; }
.node-scroll { overflow-x: auto; border-radius: var(--radius-md); border: 1px solid var(--border-light, rgba(255,255,255,.06)); }
.node-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.node-table th {
  padding: 10px 14px;
  text-align: left;
  background: var(--bg-tertiary, rgba(0,0,0,.15));
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: .02em;
  border-bottom: 1px solid var(--border-light, rgba(255,255,255,.06));
}
.node-table td {
  padding: 11px 14px;
  border-bottom: 1px solid var(--border-light, rgba(255,255,255,.04));
  transition: background var(--dur-fast);
}
.node-table tbody tr:hover { background: var(--bg-hover, rgba(255,255,255,.03)); }
.node-table tbody tr.selected { background: var(--accent-blue-soft, rgba(59,130,246,.12)); }
.node-table tbody tr:last-child td { border-bottom: none; }
.col-check { width: 40px; text-align: center; }
.col-check input[type="checkbox"] { cursor: pointer; accent-color: var(--brand); }
.td-label { font-weight: 500; color: var(--text-primary); }
.empty-cell { text-align: center; color: var(--text-tertiary); padding: 36px 0; }

/* 合并弹窗 */
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: #fff; border-radius: 14px; padding: 24px; width: 380px; box-shadow: 0 20px 60px rgba(0,0,0,.18); }
.modal-title { font-size: 16px; font-weight: 700; margin-bottom: 6px; }
.modal-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; }
.modal-label { display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; margin-top: 12px; }
.modal-input { width: 100%; margin-bottom: 4px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
</style>
