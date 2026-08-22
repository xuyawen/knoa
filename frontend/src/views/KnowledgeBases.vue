<script setup lang="ts">
// 知识库列表：知识库的增删改入口（库级管理）。
// 数据源为 useKnowledgeStore().bases（后端已按库级权限过滤，用户只看到有权限的库）。
// 成员/部门授权管理在独立的「成员管理」页（/knowledge/members），此处仅做跳转。
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import Pagination from '@/components/ui/Pagination.vue'
import DataTable from '@/components/ui/DataTable.vue'
import type { DataTableColumn } from '@/components/ui/DataTable.vue'
import RefreshButton from '@/components/ui/RefreshButton.vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { useAsyncAction } from '@/composables/useAsyncAction'
import { useDebouncedWatch } from '@/composables/useDebouncedWatch'
import { getKnowledgeBases, createKnowledgeBase, updateKnowledgeBase, deleteKnowledgeBase, getDepartments } from '@/api'
import type { KnowledgeBase, DepartmentNode, KBUpdate } from '@/types/api'

const router = useRouter()
const store = useKnowledgeStore()

// 列表列声明（全局 DataTable 组件）
const kbColumns: DataTableColumn[] = [
  { key: 'name', title: '名称', nowrap: true },
  { key: 'ownerDeptName', title: '归属部门' },
  { key: 'description', title: '描述' },
  { key: 'documentCount', title: '文档数', align: 'center', width: '80px' },
  { key: 'pendingCount', title: '待审核', align: 'center', width: '80px' },
  { key: 'ops', title: '操作', width: '130px' },
]
const auth = useAuthStore()
const toast = useToastStore()

// --- 列表数据（服务端分页 + 按名称/分类搜索） ---
const loading = ref(false)
const kbs = ref<KnowledgeBase[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const searchText = ref('') // 输入框实时值
const submitted = ref('')  // 已提交的搜索词（实际参与过滤）

async function load(force = false) {
  loading.value = true
  try {
    const res = await getKnowledgeBases(page.value, pageSize.value, submitted.value || undefined, force)
    kbs.value = res.knowledgeBases
    total.value = res.total
  } catch (e: unknown) {
    toast.error(`加载知识库列表失败：${errMsg(e)}`)
  } finally {
    loading.value = false
  }
}

function doSearch() {
  submitted.value = searchText.value.trim()
  page.value = 1
  void load()
}

// 输入即搜索（300ms 防抖）；回车立即搜索并撤销待发的防抖请求
const { cancel: cancelSearchDebounce } = useDebouncedWatch(searchText, doSearch)
function onEnterSearch() {
  cancelSearchDebounce()
  doSearch()
}

function clearSearch() {
  searchText.value = ''
  cancelSearchDebounce()
  doSearch()
}

function onPageChange(p: number) {
  page.value = p
  void load()
}

function onPageSizeChange(s: number) {
  pageSize.value = s
  page.value = 1
  void load()
}

// --- 新建 / 编辑弹窗（共用一套表单，editing 为 null 表示新建） ---
const showForm = ref(false)
const editing = ref<KnowledgeBase | null>(null)
const { busy: saving, run: runSave } = useAsyncAction()
const form = ref({ name: '', description: '', ownerDeptId: '' })
// 部门列表（超管建库/编辑时选择归属部门）
const deptOptions = ref<{ label: string; value: string }[]>([])
async function loadDepts() {
  if (deptOptions.value.length) return
  const tree = await getDepartments()
  const flat: { label: string; value: string }[] = []
  const walk = (nodes: DepartmentNode[]) => nodes.forEach(n => { flat.push({ label: n.name, value: n.id }); walk(n.children) })
  walk(tree)
  deptOptions.value = flat
}

function openCreate() {
  editing.value = null
  form.value = { name: '', description: '', ownerDeptId: '' }
  if (auth.hasPerm('kb_super')) loadDepts()
  showForm.value = true
}

function openEdit(kb: KnowledgeBase) {
  editing.value = kb
  form.value = {
    name: kb.name,
    description: kb.description || '',
    ownerDeptId: kb.ownerDeptId || '',
  }
  if (auth.hasPerm('kb_super')) loadDepts()
  showForm.value = true
}

async function submitForm() {
  const name = form.value.name.trim()
  if (!name) {
    toast.warning('请输入知识库名称')
    return
  }
  await runSave(
    async () => {
      const payload: KBUpdate & { name: string } = {
        name,
        description: form.value.description.trim() || null,
        // 归属部门：超管（kb_super）可指定/变更；非超管由后端强制本部门
        ...(auth.hasPerm('kb_super') ? { ownerDeptId: form.value.ownerDeptId || null } : {}),
      }
      if (editing.value) {
        await updateKnowledgeBase(editing.value.id, payload)
        toast.success('知识库已更新')
      } else {
        await createKnowledgeBase(payload)
        toast.success('知识库已创建')
      }
      showForm.value = false
      await store.reload() // 同步其他页面的 KB 下拉
      await load()
    },
    { onError: (e) => toast.error(`${editing.value ? '更新' : '创建'}失败：${errMsg(e)}`) },
  )
}

// --- 删除（级联清理库内全部文档/图谱，二次确认） ---
const deleteTarget = ref<KnowledgeBase | null>(null)

async function confirmDelete() {
  const kb = deleteTarget.value
  deleteTarget.value = null
  if (!kb) return
  try {
    await deleteKnowledgeBase(kb.id)
    toast.success(`已删除知识库：${kb.name}`)
    await store.reload()
    // 当前页删空时回退一页
    if (kbs.value.length <= 1 && page.value > 1) page.value -= 1
    await load()
  } catch (e: unknown) {
    toast.error(`删除失败：${errMsg(e)}`)
  }
}

// --- 跳转成员管理页（预选当前库） ---
function goMembers(kb: KnowledgeBase) {
  router.push({ path: '/knowledge/members', query: { kb: kb.id } })
}

onMounted(load)
</script>

<template>
  <div class="page kb-mgmt fade-up">
    <div class="kb-head card">
      <div class="kb-search-wrap">
        <Icon name="search" :size="15" class="kb-search-icon" />
        <input
          v-model="searchText"
          class="kb-search-input"
          placeholder="按名称或分类搜索"
          @keydown.enter="onEnterSearch"
        />
        <button v-if="searchText" class="kb-search-clear" @click="clearSearch">
          <Icon name="close" :size="12" />
        </button>
      </div>
      <div class="kb-actions">
        <RefreshButton :loading="loading" @click="load(true)" />
        <button class="btn btn-primary btn-sm" @click="openCreate">
          <Icon name="plus" :size="14" /> 新建知识库
        </button>
      </div>
    </div>

    <section class="card kb-table-card">
      <div v-if="loading && !kbs.length" class="kb-loading">
        <Icon name="loader" :size="18" class="spin" /> 加载中…
      </div>
      <DataTable v-else :columns="kbColumns" :rows="kbs" :loading="loading">
        <template #cell="{ row, col }">
          <span v-if="col.key === 'name'" class="kb-name">{{ row.name }}</span>
          <span v-else-if="col.key === 'ownerDeptName'">{{ row.ownerDeptName || '—' }}</span>
          <span v-else-if="col.key === 'description'" class="td-desc">{{ row.description || '—' }}</span>
          <span v-else-if="col.key === 'pendingCount'" :class="row.pendingCount ? 'pending-hot' : ''">{{ row.pendingCount }}</span>
          <template v-else-if="col.key === 'ops'">
            <button class="action-btn edit" title="编辑" @click="openEdit(row)">
              <Icon name="edit" :size="15" />
            </button>
            <button class="action-btn preview" title="成员管理" @click="goMembers(row)">
              <Icon name="users" :size="15" />
            </button>
            <button class="action-btn danger" title="删除" @click="deleteTarget = row">
              <Icon name="trash" :size="15" />
            </button>
          </template>
          <span v-else>{{ row[col.key] }}</span>
        </template>
      </DataTable>
      <Pagination
        v-if="total > 0"
        :page="page"
        :page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
      />
    </section>

    <!-- 新建 / 编辑弹窗 -->
    <AppModal :show="showForm" :title="editing ? '编辑知识库' : '新建知识库'" @close="showForm = false">
      <div class="form-row">
        <label class="form-label">名称</label>
        <input v-model="form.name" class="form-input" placeholder="如：运营知识库" />
      </div>
      <div class="form-row">
        <label class="form-label">归属部门</label>
        <template v-if="auth.hasPerm('kb_super')">
          <CustomSelect v-model="form.ownerDeptId" :options="deptOptions" width="100%" placeholder="选择归属部门" />
        </template>
        <template v-else>
          <span class="form-static">{{ auth.user?.department || '—' }}（自动归属本部门）</span>
        </template>
      </div>
      <div class="form-row">
        <label class="form-label">描述</label>
        <input v-model="form.description" class="form-input" placeholder="简要说明该知识库的用途（可选）" />
      </div>
      <template #foot>
        <button class="btn btn-ghost btn-sm" @click="showForm = false">取消</button>
        <button class="btn btn-primary btn-sm" :disabled="saving" @click="submitForm">
          {{ saving ? '保存中…' : editing ? '保存' : '创建' }}
        </button>
      </template>
    </AppModal>

    <!-- 删除确认 -->
    <ConfirmDialog
      :show="!!deleteTarget"
      title="删除知识库"
      :message="deleteTarget ? `确认删除知识库「${deleteTarget.name}」？将级联删除库内全部文档、向量与图谱数据，操作不可恢复。` : ''"
      confirm-text="删除"
      danger
      @close="deleteTarget = null"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
.kb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  margin-bottom: 16px;
}
.kb-actions { display: flex; align-items: center; gap: 8px; }
.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--dur-fast), color var(--dur-fast);
}
.icon-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.icon-btn:disabled { opacity: 0.5; cursor: default; }
.kb-search-wrap {
  position: relative;
  display: flex;
  align-items: center;
  width: 260px;
}
.kb-search-icon {
  position: absolute;
  left: 11px;
  color: var(--text-tertiary);
  pointer-events: none;
}
.kb-search-input {
  width: 100%;
  height: var(--btn-h-sm);
  padding: 0 30px 0 34px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 13px;
  transition: all var(--dur-fast);
}
.kb-search-input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.kb-search-input::placeholder { color: var(--text-tertiary); }
.kb-search-clear {
  position: absolute;
  right: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  color: var(--text-tertiary);
  cursor: pointer;
  background: transparent;
  border: none;
}
.kb-search-clear:hover { background: var(--bg-hover); }
.kb-table-card { padding: 0; overflow: hidden; }
.kb-loading {
  display: flex; align-items: center; gap: 8px;
  color: var(--text-tertiary); font-size: 13px; padding: 32px 20px;
}

.kb-name { font-weight: 600; color: var(--text-primary); }
.td-desc {
  color: var(--text-secondary); max-width: 340px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pending-hot { color: var(--accent-amber); font-weight: 600; }

/* 表单 */
.form-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.form-label { width: 60px; flex-shrink: 0; font-size: 13px; color: var(--text-secondary); }
.form-static { font-size: 13px; color: var(--text-primary); }
.form-input {
  flex: 1; height: 36px; padding: 0 12px; border: 1px solid var(--border); border-radius: var(--radius-md);
  font-size: 13px; background: var(--bg-surface); color: var(--text-primary); transition: all var(--dur-fast);
}
.form-input:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); }

.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
