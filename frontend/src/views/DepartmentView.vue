<script setup lang="ts">
// 部门管理：分页列表（扁平化树）+ 新增 / 编辑 / 删除。
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import DataTable from '@/components/ui/DataTable.vue'
import DepartmentTreeSelect from '@/components/ui/DepartmentTreeSelect.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import {
  getDepartments,
  createDepartment,
  updateDepartment,
  deleteDepartment,
  reorderDepartments,
} from '@/api'
import type { DepartmentOut, DepartmentNode } from '@/types/api'

const auth = useAuthStore()
const toast = useToastStore()

/* ---------- 数据加载（后端返回树，前端扁平化） ---------- */
const rawTree = ref<DepartmentNode[]>([])
const loading = ref(false)

/** 扁平化树为列表，保留 level 用于缩进展示层级关系。 */
interface FlatDept extends DepartmentOut { level: number; parentName: string }
function flatten(nodes: DepartmentNode[], level = 0, parentName = ''): FlatDept[] {
  const result: FlatDept[] = []
  for (const n of nodes) {
    result.push({ ...n, level, parentName })
    if (n.children?.length) {
      result.push(...flatten(n.children, level + 1, n.name))
    }
  }
  return result
}

const flatList = computed<FlatDept[]>(() => flatten(rawTree.value))
const totalDepts = computed(() => flatList.value.length)

async function loadDepts(force = false) {
  loading.value = true
  try {
    rawTree.value = await getDepartments(force)
  } catch (e: unknown) {
    toast.error(`加载部门失败：${errMsg(e)}`)
  } finally {
    loading.value = false
  }
}

/* ---------- 同级原生拖拽排序（不依赖外部库，用 HTML5 拖拽 API）---------- */
const tableWrap = ref<HTMLElement | null>(null)
const dragSrcId = ref<string | null>(null)
let dragSrcPid: string | null = null // dragstart 时缓存，避免 dragover 每 tick 重复 O(n) 查找
// 仅当 mousedown 落在拖拽手柄上时才“武装”拖拽，避免误触行内编辑/删除按钮。
// 注意：dragstart 的 event.target 是被拖元素（tr）本身，而非手柄，故不能用 e.target 判断手柄。
let dragArmed = false
// 落点提示：目标行 + 插入方向（按行水平中线判断），驱动插入线反馈
const dropHint = ref<{ id: string; pos: 'before' | 'after' } | null>(null)

function parentIdById(id: string): string | null {
  const d = flatList.value.find((f) => f.id === id)
  return d ? (d.parentId ?? null) : null
}

function findNodeById(nodes: DepartmentNode[], id: string): DepartmentNode | null {
  for (const n of nodes) {
    if (n.id === id) return n
    const hit = findNodeById(n.children, id)
    if (hit) return hit
  }
  return null
}

function onMouseDown(e: MouseEvent) {
  dragArmed = !!(e.target as HTMLElement).closest('.drag-handle')
}

function onDragStart(e: DragEvent) {
  const tr = (e.target as HTMLElement).closest('tr')
  if (!dragArmed || !tr) {
    e.preventDefault()
    return
  }
  const id = (tr as HTMLElement).dataset.rowkey ?? null
  if (!id) {
    e.preventDefault()
    return
  }
  dragSrcId.value = id
  dragSrcPid = parentIdById(id)
  e.dataTransfer?.setData('text/plain', id)
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}

function onDragOver(e: DragEvent) {
  const srcId = dragSrcId.value
  if (!srcId) return
  const tr = (e.target as HTMLElement).closest('tr')
  const overId = tr ? (tr as HTMLElement).dataset.rowkey : undefined
  // 仅允许同级（同一父级）之间拖动，跨层级 / 自身实时禁止
  if (!tr || !overId || overId === srcId || parentIdById(overId) !== dragSrcPid) {
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'none'
    dropHint.value = null
    return
  }
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
  e.preventDefault() // 允许 drop
  // 插入线提示：上半行→插前面，下半行→插后面（与 onDrop 共用中点判断）
  const rect = tr.getBoundingClientRect()
  const pos = e.clientY > rect.top + rect.height / 2 ? 'after' : 'before'
  if (!dropHint.value || dropHint.value.id !== overId || dropHint.value.pos !== pos) {
    dropHint.value = { id: overId, pos }
  }
}

async function onDrop(e: DragEvent) {
  const srcId = dragSrcId.value
  if (!srcId) return
  const tr = (e.target as HTMLElement).closest('tr')
  if (!tr) return
  const overId = (tr as HTMLElement).dataset.rowkey
  if (!overId || overId === srcId || parentIdById(overId) !== dragSrcPid) return
  e.preventDefault()
  const pid = dragSrcPid
  // 计算拖拽后的同级新顺序：按行水平中线把源插到目标之前/之后（修复“无法拖到同级末尾”）
  const groupIds = flatList.value
    .filter((f) => (f.parentId ?? null) === pid)
    .map((f) => f.id)
    .filter((id) => id !== srcId)
  const idx = groupIds.indexOf(overId)
  if (idx === -1) return
  const rect = tr.getBoundingClientRect()
  const insertAfter = e.clientY > rect.top + rect.height / 2
  groupIds.splice(insertAfter ? idx + 1 : idx, 0, srcId)
  clearDragState()
  // 乐观更新：本地先重排渲染，后台持久化；失败时重载回滚
  reorderLocal(pid, groupIds)
  try {
    await reorderDepartments(pid, groupIds)
  } catch (err: unknown) {
    toast.error(`排序失败：${errMsg(err)}`)
    await loadDepts(true) // 回滚顺序
  }
}

function onDragEnd() {
  clearDragState()
}

function clearDragState() {
  dragSrcId.value = null
  dragSrcPid = null
  dragArmed = false
  dropHint.value = null
}

/** 本地重排：直接调整 rawTree 对应层 children 顺序，表格立即反映新顺序（乐观更新） */
function reorderLocal(pid: string | null, orderedIds: string[]) {
  const siblings = pid === null ? rawTree.value : findNodeById(rawTree.value, pid)?.children
  if (!siblings) return
  const byId = new Map(siblings.map((n) => [n.id, n]))
  const next: DepartmentNode[] = []
  for (const id of orderedIds) {
    const n = byId.get(id)
    if (n) next.push(n)
  }
  siblings.splice(0, siblings.length, ...next)
}

/** 行 class：被拖源行置灰；目标行上/下沿显示插入线 */
function rowClass(row: FlatDept): string {
  if (dragSrcId.value && row.id === dragSrcId.value) return 'drag-src'
  const hint = dropHint.value
  if (hint && row.id === hint.id) return hint.pos === 'before' ? 'drop-before' : 'drop-after'
  return ''
}

// 数据加载 / 排序后，给行设置 draggable（事件委托到 tableWrap 容器，只绑一次）
function enableDrag() {
  const wrap = tableWrap.value
  if (!wrap) return
  wrap.querySelectorAll('tbody tr').forEach((r) => {
    const id = (r as HTMLElement).dataset.rowkey
    if (id) (r as HTMLElement).draggable = true
  })
}

onMounted(() => {
  loadDepts()
  const wrap = tableWrap.value
  if (wrap) {
    wrap.addEventListener('mousedown', onMouseDown)
    wrap.addEventListener('dragstart', onDragStart)
    wrap.addEventListener('dragover', onDragOver)
    wrap.addEventListener('drop', onDrop)
    wrap.addEventListener('dragend', onDragEnd)
  }
})

watch(flatList, () => nextTick(enableDrag))

/* ---------- 表格列定义 ---------- */
const columns = [
  { key: 'drag', title: '', width: '40px' },
  { key: 'name', title: '部门名称', strong: true },
  { key: 'parent', title: '上级部门' },
  { key: 'description', title: '描述' },
  { key: 'createdAt', title: '创建时间' },
  { key: 'actions', title: '操作' },
]

function fmtTime(s?: string) {
  if (!s) return '—'
  return s.replace('T', ' ').slice(0, 16)
}

/* ---------- 新建 / 编辑 ---------- */
const showModal = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = ref({ name: '', parentId: '', description: '' })

function openCreate() {
  editingId.value = null
  form.value = { name: '', parentId: '', description: '' }
  showModal.value = true
}
function openEdit(d: FlatDept) {
  editingId.value = d.id
  form.value = {
    name: d.name,
    parentId: d.parentId || '',
    description: d.description || '',
  }
  showModal.value = true
}

async function save() {
  if (!form.value.name.trim()) {
    toast.warning('部门名称必填')
    return
  }
  saving.value = true
  try {
    const pid = form.value.parentId || null
    if (editingId.value) {
      await updateDepartment(editingId.value, {
        name: form.value.name || undefined,
        parentId: pid,
        description: form.value.description || undefined,
      })
      toast.success('部门已更新')
    } else {
      await createDepartment({
        name: form.value.name.trim(),
        parentId: pid,
        description: form.value.description || undefined,
      })
      toast.success('部门已创建')
    }
    showModal.value = false
    await loadDepts()
  } catch (e: unknown) {
    toast.error(`操作失败：${errMsg(e)}`)
  } finally {
    saving.value = false
  }
}

/* ---------- 删除 ---------- */
const deleteTarget = ref<FlatDept | null>(null)
function onDelete(d: FlatDept) {
  deleteTarget.value = d
}
async function confirmDelete() {
  const d = deleteTarget.value
  deleteTarget.value = null
  if (!d) return
  try {
    await deleteDepartment(d.id)
    toast.success(`已删除：${d.name}`)
    await loadDepts()
  } catch (e: unknown) {
    toast.error(`删除失败：${errMsg(e)}`)
  }
}
</script>

<template>
  <div class="page dept fade-up">
    <div class="card dept-card">
    <!-- 工具栏 -->
    <div class="toolbar">
      <span class="dept-count">共 {{ totalDepts }} 个部门</span>
      <button type="button" class="icon-btn" title="刷新" :disabled="loading" @click="loadDepts(true)">
        <Icon name="refresh" :size="15" :class="{ spin: loading }" />
      </button>
      <button v-if="auth.hasPerm('user_manage')" class="btn btn-primary btn-sm" style="margin-left:auto" @click="openCreate">
        <Icon name="plus" :size="13" /> 新增部门
      </button>
    </div>

    <!-- 表格 -->
    <div ref="tableWrap" class="dept-table-wrap">
    <DataTable
      :columns="columns"
      :rows="flatList"
      row-key="id"
      :loading="loading"
      :row-class="rowClass"
    >
      <template #cell="{ row, col }">
        <template v-if="col.key === 'drag'">
          <span class="drag-handle" title="拖动调整同级顺序"><Icon name="grip-vertical" :size="16" /></span>
        </template>
        <template v-else-if="col.key === 'name'">
          <span class="dept-indent" :style="{ paddingLeft: `${row.level * 24}px` }">
            <span class="dept-name">{{ row.name }}</span>
          </span>
        </template>
        <template v-else-if="col.key === 'parent'">{{ row.parentName || '—' }}</template>
        <template v-else-if="col.key === 'description'">{{ row.description || '—' }}</template>
        <template v-else-if="col.key === 'createdAt'">{{ fmtTime(row.createdAt) }}</template>
        <template v-else-if="col.key === 'actions'">
          <div class="row-actions">
            <button class="action-btn edit" title="编辑" @click="openEdit(row)"><Icon name="edit" :size="15" /></button>
            <button v-if="auth.hasPerm('user_manage')" class="action-btn danger" title="删除" @click="onDelete(row)">
              <Icon name="trash" :size="15" />
            </button>
          </div>
        </template>
      </template>
      <template #empty>暂无部门数据</template>
    </DataTable>
    </div>
    </div>

    <!-- 新建 / 编辑弹窗 -->
    <AppModal :show="showModal" :title="editingId ? '编辑部门' : '新增部门'" @close="showModal = false">
      <div class="form-row">
        <label class="form-label">部门名称 <span class="required">*</span></label>
        <input v-model="form.name" class="form-input" placeholder="请输入部门名称" />
      </div>
      <div class="form-row">
        <label class="form-label">上级部门</label>
        <!-- 复用文档管理的树状部门选择器；编辑时排除自身及后代（防循环），顶部项为「（无/顶级）」 -->
        <DepartmentTreeSelect
          v-model="form.parentId"
          :nodes="rawTree"
          placeholder="（无/顶级）"
          top-label="（无/顶级）"
          :exclude-id="editingId"
          block
        />
      </div>
      <div class="form-row">
        <label class="form-label">描述</label>
        <input v-model="form.description" class="form-input" placeholder="可选" />
      </div>
      <template #foot>
        <button class="btn btn-ghost btn-sm" @click="showModal = false">取消</button>
        <button class="btn btn-primary btn-sm" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </template>
    </AppModal>

    <!-- 删除确认 -->
    <ConfirmDialog
      :show="!!deleteTarget"
      title="删除部门"
      :message="deleteTarget ? `确认删除部门「${deleteTarget.name}」？若有子部门或关联文档则无法删除。` : ''"
      confirm-text="删除"
      danger
      @close="deleteTarget = null"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
.dept-card { padding: 20px; }

.dept-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.dept-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.dept-count {
  font-size: 13px;
  color: var(--text-tertiary);
}

/* ---- 表格 ---- */
.dept-indent {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.tree-icon {
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.dept-name {
  font-weight: 500;
  color: var(--text-primary);
}

.row-actions { display: flex; align-items: center; gap: 4px; }

.icon-btn:disabled { opacity: 0.5; cursor: default; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ---- 表单 ---- */
.form-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.form-label {
  width: 80px; flex-shrink: 0; font-size: 13px; color: var(--text-secondary);
}
.required { color: var(--danger); }
.form-input {
  flex: 1; height: 36px; padding: 0 12px; border: 1px solid var(--border); border-radius: var(--radius-md);
  font-size: 13px; background: var(--bg-surface); color: var(--text-primary); transition: all var(--dur-fast);
}
.form-input:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); }

/* ---- 拖拽排序手柄 ---- */
.drag-handle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  color: var(--text-tertiary);
  opacity: 0.4;
  transition: opacity var(--dur-fast), color var(--dur-fast);
}
.drag-handle:hover { opacity: 1; color: var(--brand); }
.drag-handle:active { cursor: grabbing; }
.dept-table-wrap tbody tr:hover .drag-handle { opacity: 1; }

/* ---- 拖拽排序反馈（tr/td 是 DataTable 子组件内部元素，需 :deep 穿透 scoped）---- */
.dept-table-wrap :deep(tbody tr.drag-src) { opacity: 0.4; }
.dept-table-wrap :deep(tbody tr.drop-before td) { box-shadow: inset 0 2px 0 var(--brand); }
.dept-table-wrap :deep(tbody tr.drop-after td) { box-shadow: inset 0 -2px 0 var(--brand); }
</style>
