<script setup lang="ts">
// 部门管理：分页列表（扁平化树）+ 新增 / 编辑 / 删除。
import { ref, computed, onMounted } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import Pagination from '@/components/ui/Pagination.vue'
import DataTable from '@/components/ui/DataTable.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import {
  getDepartments,
  createDepartment,
  updateDepartment,
  deleteDepartment,
} from '@/api'
import type { DepartmentOut, DepartmentNode } from '@/types/api'

const auth = useAuthStore()
const toast = useToastStore()

/* ---------- 数据加载（后端返回树，前端扁平化做分页） ---------- */
const rawTree = ref<DepartmentNode[]>([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)

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

const pagedDepts = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return flatList.value.slice(start, start + pageSize.value)
})

async function loadDepts() {
  loading.value = true
  try {
    rawTree.value = await getDepartments()
  } catch (e: any) {
    toast.error(`加载部门失败：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

onMounted(loadDepts)

/* ---------- 表格列定义 ---------- */
const columns = [
  { key: 'name', title: '部门名称', strong: true },
  { key: 'parent', title: '上级部门' },
  { key: 'description', title: '描述' },
  { key: 'sortOrder', title: '排序' },
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
const form = ref({ name: '', parentId: '', description: '', sortOrder: 0 })

/** 扁平选项列表（用于父级下拉），排除自己及后代（编辑时）。 */
const parentOptions = computed(() => {
  const opts = [{ label: '（无/顶级）', value: '' }]
  function walk(nodes: DepartmentNode[]) {
    for (const n of nodes) {
      if (editingId.value && n.id === editingId.value) continue
      opts.push({ label: n.name, value: n.id })
      if (n.children?.length) walk(n.children)
    }
  }
  walk(rawTree.value)
  return opts
})

function openCreate() {
  editingId.value = null
  form.value = { name: '', parentId: '', description: '', sortOrder: 0 }
  showModal.value = true
}
function openEdit(d: FlatDept) {
  editingId.value = d.id
  form.value = {
    name: d.name,
    parentId: d.parentId || '',
    description: d.description || '',
    sortOrder: d.sortOrder,
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
        sortOrder: form.value.sortOrder,
      })
      toast.success('部门已更新')
    } else {
      await createDepartment({
        name: form.value.name.trim(),
        parentId: pid,
        description: form.value.description || undefined,
        sortOrder: form.value.sortOrder,
      })
      toast.success('部门已创建')
    }
    showModal.value = false
    await loadDepts()
  } catch (e: any) {
    toast.error(`操作失败：${e?.message || e}`)
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
  } catch (e: any) {
    toast.error(`删除失败：${e?.message || e}`)
  }
}
</script>

<template>
  <div class="page dept fade-up">
    <div class="card dept-card">
    <!-- 标题栏 -->
    <div class="dept-head">
      <h3 class="dept-title">部门管理</h3>
      <button v-if="auth.isAdmin" class="btn btn-primary btn-sm" @click="openCreate">
        <Icon name="plus" :size="13" /> 新增部门
      </button>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <span class="dept-count">共 {{ totalDepts }} 个部门</span>
      <button class="icon-btn" title="刷新" :disabled="loading" @click="loadDepts()">
        <Icon name="refresh" :size="15" :class="{ spin: loading }" />
      </button>
    </div>

    <!-- 表格 -->
    <DataTable
      :columns="columns"
      :rows="pagedDepts"
      row-key="id"
      :loading="loading"
    >
      <template #cell="{ row, col }">
        <template v-if="col.key === 'name'">
          <span class="dept-indent" :style="{ paddingLeft: `${row.level * 24}px` }">
            <Icon v-if="row.level > 0" name="corner-down-right" :size="14" class="tree-icon" />
            <span class="dept-name">{{ row.name }}</span>
          </span>
        </template>
        <template v-else-if="col.key === 'parent'">{{ row.parentName || '—' }}</template>
        <template v-else-if="col.key === 'description'">{{ row.description || '—' }}</template>
        <template v-else-if="col.key === 'sortOrder'">{{ row.sortOrder }}</template>
        <template v-else-if="col.key === 'createdAt'">{{ fmtTime(row.createdAt) }}</template>
        <template v-else-if="col.key === 'actions'">
          <div class="row-actions">
            <button class="action-btn" title="编辑" @click="openEdit(row)"><Icon name="edit" :size="15" /></button>
            <button v-if="auth.isAdmin" class="action-btn danger" title="删除" @click="onDelete(row)">
              <Icon name="trash" :size="15" />
            </button>
          </div>
        </template>
      </template>
      <template #empty>暂无部门数据</template>
    </DataTable>

    <!-- 分页 -->
    <Pagination
      v-if="totalDepts > 0"
      v-model:page="currentPage"
      v-model:page-size="pageSize"
      :total="totalDepts"
    />
    </div>

    <!-- 新建 / 编辑弹窗 -->
    <AppModal :show="showModal" :title="editingId ? '编辑部门' : '新增部门'" @close="showModal = false">
      <div class="form-row">
        <label class="form-label">部门名称 <span class="required">*</span></label>
        <input v-model="form.name" class="form-input" placeholder="请输入部门名称" />
      </div>
      <div class="form-row">
        <label class="form-label">上级部门</label>
        <CustomSelect v-model="form.parentId" :options="parentOptions" />
      </div>
      <div class="form-row">
        <label class="form-label">描述</label>
        <input v-model="form.description" class="form-input" placeholder="可选" />
      </div>
      <div class="form-row">
        <label class="form-label">排序</label>
        <input v-model.number="form.sortOrder" type="number" class="form-input" min="0" style="width:120px" />
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
.action-btn {
  display: flex; align-items: center; justify-content: center; width: 28px; height: 28px;
  border-radius: var(--radius-sm); color: var(--text-secondary); background: transparent; cursor: pointer; transition: all var(--dur-fast);
}
.action-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.action-btn.danger:hover { background: var(--danger-soft); color: var(--danger); }

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
</style>
