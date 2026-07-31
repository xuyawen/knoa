<script setup lang="ts">
// 知识图谱 — 节点管理视图（实体表格 + 分页 + 多选合并）。
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import Pagination from '@/components/ui/Pagination.vue'
import Icon from '@/components/ui/Icon.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import { useGraphData } from '@/composables/useGraphData'
import { useBackdropClick } from '@/composables/useBackdropClick'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import type { GraphMergePreview } from '@/types/api'
import '@/assets/graph.css'

const {
  graph, pagedNodes, degree, kbName,
  nodePage, nodePageSize, mergeNodes, previewMerge, selectedId,
  nodeFilterKb, nodeFilterTerm, nodeFilterType, nodeTableTypeOpts, hasNodeFilter,
  nodeTotal, fetchNodeList,
  bizCatOpts,
  rebuildProgress,
} = useGraphData()
const auth = useAuthStore()
const toast = useToastStore()

// 节点列表走服务端分页/过滤，挂载时拉取当前页
onMounted(() => { void fetchNodeList() })

/* ---- 节点表筛选栏 ---- */
// 知识库下拉：列全部可访问知识库（节点表走服务端全集，不能只看画布采样里出现的库）
const kbFilterOpts = computed<{ label: string; value: string }[]>(() => [
  { label: '全部知识库', value: '' },
  ...bizCatOpts.value,
])
function clearNodeFilters() {
  nodeFilterKb.value = ''
  nodeFilterTerm.value = ''
  nodeFilterType.value = ''
}

/* ---- 多选 + 合并 ---- */
const selectedIds = ref<Set<string>>(new Set())
const mergeDialogVisible = ref(false)
const mergeBd = useBackdropClick(() => { mergeDialogVisible.value = false })
const mergeLabel = ref('')
const mergeType = ref('')

// 跨库检测：选中节点分属多个知识库。合并按 KB 进行，跨库选择会被后端静默丢弃
// 其他库的节点（造成部分合并），故前端必须拦截
const crossKb = computed(() => {
  const kbs = new Set(
    (graph.value?.nodes || [])
      .filter(n => selectedIds.value.has(n.id))
      .map(n => n.kbId),
  )
  return kbs.size > 1
})
// 合并仅 admin 可用（后端 _require_kb_write(..., "admin")），按钮同步门控，避免非管理员点了确认才收到 403
const canMerge = computed(() => auth.hasPerm('graph_manage') && selectedIds.value.size >= 2 && !crossKb.value)
const mergeDisabledHint = computed(() => {
  if (!auth.hasPerm('graph_manage')) return '无图谱管理权限，无法合并实体'
  if (crossKb.value) return '不能跨知识库合并，请仅选择同一知识库内的实体'
  if (selectedIds.value.size < 2) return '请至少选择 2 个实体'
  return ''
})

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
/* ---- 合并预览（P1：先预览影响，再确认合并） ---- */
// 选中实体清单按度数降序——度数最高的实体连接最多、最具代表性，其 label 作为推荐目标名
const selectedNodes = computed(() =>
  (graph.value?.nodes || [])
    .filter(n => selectedIds.value.has(n.id))
    .sort((a, b) => (degree.value[b.id] || 0) - (degree.value[a.id] || 0)),
)
const suggestedLabel = computed(() => selectedNodes.value[0]?.label || '')

const preview = ref<GraphMergePreview | null>(null)
const previewing = ref(false)
const mergeBusy = ref(false)
let previewTimer: ReturnType<typeof setTimeout> | null = null
let previewSeq = 0

// 防抖预览：用户停止输入 300ms 后才请求，避免每次击键都打后端；seq 丢弃过期响应防竞态
function schedulePreview() {
  if (previewTimer) clearTimeout(previewTimer)
  previewTimer = setTimeout(async () => {
    previewTimer = null
    const label = mergeLabel.value.trim()
    if (!label || selectedIds.value.size < 2) { preview.value = null; previewing.value = false; return }
    const seq = ++previewSeq
    previewing.value = true
    const res = await previewMerge([...selectedIds.value], label)
    if (seq !== previewSeq) return // 已有更新的请求，丢弃过期结果
    preview.value = res
    previewing.value = false
  }, 300)
}
watch(mergeLabel, schedulePreview)
onUnmounted(() => { if (previewTimer) clearTimeout(previewTimer) })

function openMerge() {
  if (!canMerge.value) return
  mergeLabel.value = suggestedLabel.value // 预填推荐名，用户可直接确认或改写
  mergeType.value = ''
  preview.value = null
  mergeDialogVisible.value = true
  schedulePreview() // mergeLabel 若与旧值相同 watch 不会触发，这里兜底
}
async function confirmMerge() {
  if (!mergeLabel.value.trim() || mergeBusy.value) return
  mergeBusy.value = true
  const res = await mergeNodes([...selectedIds.value], mergeLabel.value.trim(), mergeType.value.trim() || undefined)
  mergeBusy.value = false
  if (!res) return
  mergeDialogVisible.value = false
  selectedIds.value = new Set()
  // 结构化摘要：明确告知“发生了什么”，合并不再是黑盒
  const parts = [`已合并 ${res.merged} 个实体为「${res.target.label}」`]
  if (res.edgesRedirected) parts.push(`重定向 ${res.edgesRedirected} 条关系`)
  const cleaned = res.selfLoopsRemoved + res.duplicateEdgesRemoved
  if (cleaned) parts.push(`清理 ${cleaned} 条冗余关系`)
  toast.success(parts.join('，'))
  // 高亮合并目标节点，让用户立刻在图谱上看到结果
  selectedId.value = res.target.id
}
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
    <div class="card node-card">
      <div class="panel-head">
        <span class="panel-title">实体节点（{{ nodeTotal }}）</span>
        <button class="btn btn-sm" :class="canMerge ? 'btn-primary' : 'btn-ghost'" :disabled="!canMerge" :title="mergeDisabledHint" @click="openMerge">
          <Icon name="layers" :size="13" /> 合并{{ selectedIds.size >= 2 ? `（${selectedIds.size}）` : '' }}
        </button>
      </div>
      <!-- 筛选栏：知识库 / 名称 / 类型（客户端即时过滤） -->
      <div class="node-filter-bar">
        <CustomSelect v-model="nodeFilterKb" :options="kbFilterOpts" placeholder="全部知识库" width="150px" />
        <div class="g-search node-search">
          <input v-model="nodeFilterTerm" type="text" placeholder="搜索实体名称…" class="g-input" />
          <Icon name="search" :size="15" class="g-search-icon" />
        </div>
        <CustomSelect v-model="nodeFilterType" :options="nodeTableTypeOpts" placeholder="全部类型" width="130px" />
        <button v-if="hasNodeFilter" class="btn btn-ghost btn-sm" @click="clearNodeFilters">重置</button>
      </div>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th class="col-check"><input type="checkbox" :checked="allPageSelected" @change="toggleSelectAll" /></th>
              <th>实体</th><th>类型</th><th>知识库</th><th>度数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in pagedNodes" :key="row.id" :class="{ 'is-selected': selectedIds.has(row.id) }">
              <td class="col-check"><input type="checkbox" :checked="selectedIds.has(row.id)" @change="toggleSelect(row.id)" /></td>
              <td class="td-label">{{ row.label }}</td>
              <td>{{ row.type || '—' }}</td>
              <td>{{ kbName(row.kbId) }}</td>
              <td>{{ degree[row.id] || 0 }}</td>
            </tr>
            <tr v-if="!pagedNodes.length"><td colspan="5" class="empty-cell">{{ hasNodeFilter ? '无匹配的实体节点' : '暂无实体节点' }}</td></tr>
          </tbody>
        </table>
      </div>
      <Pagination
        v-if="nodeTotal > 0"
        v-model:page="nodePage"
        v-model:page-size="nodePageSize"
        :total="nodeTotal"
        :page-sizes="[10, 15, 30]"
      />
    </div>

    <!-- 合并弹窗（P1：预览面板——先看影响，再确认合并） -->
    <Teleport to="body">
      <div v-if="mergeDialogVisible" class="modal-mask" @mousedown="mergeBd.onMouseDown" @mouseup="mergeBd.onMouseUp">
        <div class="modal-box merge-modal">
          <div class="modal-title">合并实体</div>
          <p class="modal-desc">将已选的 {{ selectedNodes.length }} 个实体合并为一个节点，所有关联关系将重定向。操作不可撤销，请确认预览影响后再继续。</p>

          <label class="modal-label">已选实体（{{ selectedNodes.length }}）</label>
          <div class="merge-source-list">
            <div v-for="n in selectedNodes" :key="n.id" class="merge-source-item">
              <span class="merge-source-name">{{ n.label }}</span>
              <span v-if="n.type" class="merge-source-type">{{ n.type }}</span>
              <span class="merge-source-degree">{{ degree[n.id] || 0 }} 条关系</span>
            </div>
          </div>

          <label class="modal-label">目标名称</label>
          <input v-model="mergeLabel" class="g-input modal-input" placeholder="合并后的实体名称" />
          <p v-if="suggestedLabel && mergeLabel.trim() !== suggestedLabel" class="merge-hint">
            推荐：<a href="#" @click.prevent="mergeLabel = suggestedLabel">{{ suggestedLabel }}</a>（度数最高）
          </p>
          <label class="modal-label">类型（可选）</label>
          <input v-model="mergeType" class="g-input modal-input" placeholder="如：流程 / 概念 / 产品" />

          <!-- 预览影响：与后端 merge 共用同一套规则，所见即所得 -->
          <div v-if="previewing" class="merge-preview is-loading">正在计算合并影响…</div>
          <div v-else-if="preview" class="merge-preview">
            <div v-if="preview.targetExists" class="merge-notice is-info">
              「{{ mergeLabel.trim() }}」已存在——将并入该现有节点，而非新建
            </div>
            <div v-if="preview.typeConflict" class="merge-notice is-warn">
              所选实体类型不一致（{{ preview.sourceTypes.join(' / ') }}），建议合并后手动指定类型
            </div>
            <div class="merge-stats">
              <div class="merge-stat"><b>{{ preview.nodesRemoved }}</b><span>移除实体</span></div>
              <div class="merge-stat"><b>{{ preview.edgesRedirected }}</b><span>重定向关系</span></div>
              <div class="merge-stat"><b>{{ preview.selfLoopsRemoved }}</b><span>清理自环</span></div>
              <div class="merge-stat"><b>{{ preview.duplicateEdgesRemoved }}</b><span>清理重复</span></div>
            </div>
          </div>

          <div class="modal-actions">
            <button class="btn btn-ghost btn-sm" @click="mergeDialogVisible = false">取消</button>
            <button class="btn btn-primary btn-sm" :disabled="!mergeLabel.trim() || previewing || mergeBusy" @click="confirmMerge">
              {{ mergeBusy ? '合并中…' : '确认合并' }}
            </button>
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

/* 筛选栏：知识库 / 名称搜索 / 类型 */
.node-filter-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.node-search { width: 220px; }

/* 复用全局 DataTable 样式，仅保留节点页特有覆盖 */
.data-table-wrap { width: 100%; overflow-x: auto; border-radius: 0 0 var(--radius-lg) var(--radius-lg); }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
  text-align: left;
  padding: 11px 14px;
  color: var(--text-tertiary);
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.02em;
  white-space: nowrap;
  border-bottom: 1px solid var(--border);
}
.data-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  vertical-align: middle;
}
.data-table tbody tr:hover { background: var(--bg-hover); }
.data-table tbody tr.is-selected { background: var(--brand-soft); }
.data-table tbody tr:last-child td { border-bottom: none; }
.col-check { width: 44px; padding-left: 14px; padding-right: 8px; text-align: center; }
.col-check input[type="checkbox"] { width: 15px; height: 15px; cursor: pointer; accent-color: var(--brand); }
.td-label { font-weight: 600; color: var(--text-primary); }
.empty-cell { text-align: center; color: var(--text-tertiary); padding: 32px 14px; font-size: 13px; opacity: 0.5; }

/* 合并弹窗 */
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: var(--bg-surface); border-radius: 14px; padding: 24px; width: 380px; box-shadow: var(--shadow-pop); }
.modal-title { font-size: 16px; font-weight: 700; margin-bottom: 6px; }
.modal-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 16px; }
.modal-label { display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; margin-top: 12px; }
.modal-input { width: 100%; margin-bottom: 4px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }

/* 合并弹窗——预览面板 */
.merge-modal { width: 440px; }
.merge-source-list { max-height: 148px; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px; padding: 4px; }
.merge-source-item { display: flex; align-items: center; gap: 8px; padding: 6px 8px; font-size: 13px; border-radius: 6px; }
.merge-source-item + .merge-source-item { margin-top: 2px; }
.merge-source-item:hover { background: var(--bg-hover); }
.merge-source-name { flex: 1; font-weight: 600; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.merge-source-type { font-size: 11px; color: var(--text-tertiary); background: var(--bg-subtle); border-radius: 4px; padding: 1px 6px; white-space: nowrap; }
.merge-source-degree { font-size: 11px; color: var(--text-tertiary); white-space: nowrap; }
.merge-hint { font-size: 12px; color: var(--text-tertiary); margin-top: 4px; }
.merge-hint a { color: var(--brand); text-decoration: none; font-weight: 600; }
.merge-preview { margin-top: 14px; border: 1px solid var(--border); border-radius: 10px; padding: 12px; background: var(--bg-subtle); }
.merge-preview.is-loading { font-size: 12px; color: var(--text-tertiary); text-align: center; padding: 16px 12px; }
.merge-notice { font-size: 12px; line-height: 1.5; border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; }
.merge-notice.is-info { color: var(--info); background: var(--info-soft); }
.merge-notice.is-warn { color: var(--warning); background: var(--warning-soft); }
.merge-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.merge-stat { text-align: center; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px; padding: 8px 4px; }
.merge-stat b { display: block; font-size: 16px; color: var(--text-primary); }
.merge-stat span { font-size: 11px; color: var(--text-tertiary); }
</style>
