<script setup lang="ts">
// 权限管理（对应架构图 #7）：真实用户/角色管理 + 后端固定 RBAC 策略参考矩阵。
import { ref, computed, onMounted, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import Pagination from '@/components/ui/Pagination.vue'
import DataTable from '@/components/ui/DataTable.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { getUserList, createUser, updateUser, deleteUser } from '@/api/auth'
import type { Paginated, UserOut, UserCreate, UserUpdate } from '@/types/api'

const auth = useAuthStore()
const toast = useToastStore()

/* ---------- 用户列表（服务端分页） ---------- */
const usersData = ref<Paginated<UserOut> | null>(null)
const loading = ref(false)
const searchQuery = ref('')
const roleFilter = ref<'all' | 'admin' | 'editor' | 'viewer'>('all')
const currentPage = ref(1)
const pageSize = ref(20)

async function loadUsers(resetPage = false) {
  if (resetPage) currentPage.value = 1
  loading.value = true
  try {
    usersData.value = await getUserList(
      currentPage.value,
      pageSize.value,
      roleFilter.value === 'all' ? null : roleFilter.value,
      searchQuery.value.trim() || null,
    )
  } catch (e: any) {
    usersData.value = null
    toast.error(`加载用户列表失败：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => loadUsers())

const pagedUsers = computed(() => usersData.value?.items ?? [])
const totalUsers = computed(() => usersData.value?.total ?? 0)
const userColumns = [
  { key: 'username', title: '用户名', strong: true },
  { key: 'displayName', title: '显示名' },
  { key: 'email', title: '邮箱' },
  { key: 'department', title: '部门' },
  { key: 'employeeId', title: '工号' },
  { key: 'role', title: '角色' },
  { key: 'isActive', title: '状态' },
  { key: 'actions', title: '操作' },
]
function clearSearch() {
  searchQuery.value = ''
  loadUsers(true)
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadUsers(true), 250)
})
watch([roleFilter, pageSize], () => loadUsers(true))

/* ---------- 角色样式 ---------- */
function roleClass(r: string) {
  return r === 'admin' ? 'role-admin' : r === 'editor' ? 'role-editor' : 'role-viewer'
}
const ROLE_LABEL: Record<string, string> = { admin: '管理员', editor: '编辑者', viewer: '访客' }

/* ---------- 新建 / 编辑 ---------- */
const showModal = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = ref({ username: '', displayName: '', role: 'viewer', password: '', isActive: true, email: '', department: '', employeeId: '' })

function openCreate() {
  editingId.value = null
  form.value = { username: '', displayName: '', role: 'viewer', password: '', isActive: true, email: '', department: '', employeeId: '' }
  showModal.value = true
}
function openEdit(u: UserOut) {
  editingId.value = u.id
  form.value = {
    username: u.username,
    displayName: u.displayName || '',
    role: u.role,
    password: '',
    isActive: u.isActive,
    email: u.email || '',
    department: u.department || '',
    employeeId: u.employeeId || '',
  }
  showModal.value = true
}

async function save() {
  if (!form.value.username.trim()) {
    toast.warning('用户名必填')
    return
  }
  if (!editingId.value && !form.value.password) {
    toast.warning('请设置初始密码')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      const payload: UserUpdate = {
        displayName: form.value.displayName || null,
        role: form.value.role,
        isActive: form.value.isActive,
        email: form.value.email || null,
        department: form.value.department || null,
        employeeId: form.value.employeeId || null,
      }
      if (form.value.password) payload.password = form.value.password
      await updateUser(editingId.value, payload)
      toast.success('用户已更新')
    } else {
      const payload: UserCreate = {
        username: form.value.username.trim(),
        password: form.value.password,
        displayName: form.value.displayName || null,
        role: form.value.role,
        email: form.value.email || null,
        department: form.value.department || null,
        employeeId: form.value.employeeId || null,
      }
      await createUser(payload)
      toast.success('用户已创建')
    }
    showModal.value = false
    await loadUsers()
  } catch (e: any) {
    toast.error(`操作失败：${e?.message || e}`)
  } finally {
    saving.value = false
  }
}

/* ---------- 删除 ---------- */
const deleteTarget = ref<UserOut | null>(null)
function onDelete(u: UserOut) {
  if (u.id === auth.user?.id) {
    toast.warning('不能删除当前登录账号')
    return
  }
  deleteTarget.value = u
}
async function confirmDelete() {
  const u = deleteTarget.value
  deleteTarget.value = null
  if (!u) return
  try {
    await deleteUser(u.id)
    toast.success(`已删除：${u.username}`)
    await loadUsers()
  } catch (e: any) {
    toast.error(`删除失败：${e?.message || e}`)
  }
}

/* ---------- 筛选项 / 角色分段（常量） ---------- */
const roleFilterOptions = ['all', 'admin', 'editor', 'viewer'] as const
const roleSegOptions = ['viewer', 'editor', 'admin'] as const

/* ---------- 静态 RBAC 参考矩阵（后端固定策略） ---------- */
const modules = ['知识库查看', '文档上传', '文档编辑', '文档删除', 'AI 问答', '图谱管理', '用户管理', '系统设置']
const roleMatrix = [
  { name: '管理员', key: 'admin', perms: [true, true, true, true, true, true, true, true] },
  { name: '编辑者', key: 'editor', perms: [true, true, true, false, true, true, false, false] },
  { name: '访客', key: 'viewer', perms: [true, false, false, false, true, false, false, false] },
]
</script>

<template>
  <div class="page perm fade-up">
    <div class="perm-body">
      <!-- 用户管理 -->
      <section class="card perm-users">
        <div class="perm-h-row">
          <h3 class="perm-h">用户与角色</h3>
          <button v-if="auth.isAdmin" class="btn btn-primary btn-sm" @click="openCreate">
            <Icon name="plus" :size="13" /> 新建用户
          </button>
        </div>

        <div class="toolbar">
          <div class="search-box">
            <Icon name="search" :size="14" class="search-icon" />
            <input v-model="searchQuery" type="text" placeholder="搜索用户名 / 显示名" class="search-input" />
            <button v-if="searchQuery" class="search-clear" @click="clearSearch"><Icon name="close" :size="12" /></button>
          </div>
          <div class="role-tabs">
            <button
              v-for="r in roleFilterOptions"
              :key="r"
              class="role-tab"
              :class="{ active: roleFilter === r }"
              @click="roleFilter = r; currentPage = 1"
            >{{ r === 'all' ? '全部' : ROLE_LABEL[r] }}</button>
          </div>
          <button class="icon-btn" title="刷新" :disabled="loading" @click="() => loadUsers()">
            <Icon name="refresh" :size="15" :class="{ spin: loading }" />
          </button>
        </div>

        <DataTable
          :columns="userColumns"
          :rows="pagedUsers"
          row-key="id"
          :loading="loading"
        >
          <template #cell="{ row, col }">
            <template v-if="col.key === 'username'">
              <span class="u-avatar">{{ (row.displayName || row.username)[0]?.toUpperCase() }}</span>
              <span class="u-uname">{{ row.username }}</span>
            </template>
            <template v-else-if="col.key === 'displayName'">{{ row.displayName || '—' }}</template>
            <template v-else-if="col.key === 'email'">{{ row.email || '—' }}</template>
            <template v-else-if="col.key === 'department'">{{ row.department || '—' }}</template>
            <template v-else-if="col.key === 'employeeId'">{{ row.employeeId || '—' }}</template>
            <template v-else-if="col.key === 'role'">
              <span class="role-badge" :class="roleClass(row.role)">{{ ROLE_LABEL[row.role] || row.role }}</span>
            </template>
            <template v-else-if="col.key === 'isActive'">
              <span class="status-badge" :class="row.isActive ? 'success' : 'danger'">{{ row.isActive ? '启用' : '停用' }}</span>
            </template>
            <template v-else-if="col.key === 'actions'">
              <div class="row-actions">
                <button class="action-btn" title="编辑" @click="openEdit(row)"><Icon name="edit" :size="15" /></button>
                <button class="action-btn" title="删除" @click="onDelete(row)"><Icon name="trash" :size="15" /></button>
              </div>
            </template>
          </template>
          <template #empty>暂无用户（或当前筛选无匹配）</template>
        </DataTable>

        <Pagination
          v-if="totalUsers > 0"
          v-model:page="currentPage"
          v-model:page-size="pageSize"
          :total="totalUsers"
          @update:page="loadUsers()"
          @update:page-size="loadUsers(true)"
        />
      </section>

      <!-- 角色权限矩阵（后端固定策略参考） -->
      <aside class="card perm-matrix">
        <h3 class="perm-h">角色权限矩阵</h3>
        <table class="mtx">
          <thead>
            <tr>
              <th>功能模块</th>
              <th v-for="r in roleMatrix" :key="r.key">{{ r.name }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(m, mi) in modules" :key="mi">
              <td class="mtx-mod">{{ m }}</td>
              <td v-for="r in roleMatrix" :key="r.key">
                <span class="sw" :class="r.perms[mi] ? 'on' : 'off'"><span class="knob" /></span>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="perm-note">矩阵为后端固定 RBAC 策略（角色→能力映射），与用户管理实时同步；具体能力由服务端强制执行。</p>
      </aside>
    </div>

    <!-- 新建 / 编辑弹窗 -->
    <AppModal :show="showModal" :title="editingId ? '编辑用户' : '新建用户'" @close="showModal = false">
      <div class="form-row">
        <label class="form-label">用户名</label>
        <input
          v-model="form.username"
          class="form-input"
          :disabled="!!editingId"
          placeholder="登录账号"
        />
      </div>
      <div class="form-row">
        <label class="form-label">显示名</label>
        <input v-model="form.displayName" class="form-input" placeholder="可选" />
      </div>
      <div class="form-row">
        <label class="form-label">邮箱</label>
        <input v-model="form.email" class="form-input" placeholder="可选" />
      </div>
      <div class="form-row">
        <label class="form-label">部门</label>
        <input v-model="form.department" class="form-input" placeholder="可选" />
      </div>
      <div class="form-row">
        <label class="form-label">工号</label>
        <input v-model="form.employeeId" class="form-input" placeholder="可选" />
      </div>
      <div class="form-row">
        <label class="form-label">角色</label>
        <div class="seg">
          <button
            v-for="r in roleSegOptions"
            :key="r"
            class="seg-btn"
            :class="{ active: form.role === r }"
            @click="form.role = r"
          >{{ ROLE_LABEL[r] }}</button>
        </div>
      </div>
      <div class="form-row">
        <label class="form-label">{{ editingId ? '重置密码' : '初始密码' }}</label>
        <input
          v-model="form.password"
          type="password"
          class="form-input"
          :placeholder="editingId ? '留空则不修改' : '必填'"
        />
      </div>
      <div class="form-row" v-if="editingId">
        <label class="form-label">账号状态</label>
        <label class="switch">
          <input type="checkbox" v-model="form.isActive" />
          <span class="switch-track"><span class="switch-knob" /></span>
          <span class="switch-text">{{ form.isActive ? '启用' : '停用' }}</span>
        </label>
      </div>
      <template #foot>
        <button class="btn btn-ghost btn-sm" @click="showModal = false">取消</button>
        <button class="btn btn-primary btn-sm" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </template>
    </AppModal>

    <ConfirmDialog
      :show="!!deleteTarget"
      title="删除用户"
      :message="deleteTarget ? `确认删除用户「${deleteTarget.username}」？该操作不可恢复。` : ''"
      confirm-text="删除"
      danger
      @close="deleteTarget = null"
      @confirm="confirmDelete"
    />

  </div>
</template>

<style scoped>
.page { padding: 20px 24px; }
.flex { display: flex; }
.items-center { align-items: center; }
.perm-body {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 16px;
  align-items: start;
}
.perm-users { padding: 20px 22px; }
.perm-h { margin: 0 0 14px; font-size: 15px; font-weight: 600; color: var(--text-primary); }
.perm-h-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.perm-h-row .perm-h { margin: 0; }

/* ---- 用户表工具栏 ---- */
.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.search-box { position: relative; width: 220px; }
.search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--text-tertiary); pointer-events: none; }
.search-input {
  width: 100%; height: 34px; padding: 0 30px 0 32px;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  font-size: 13px; background: var(--bg-surface); transition: all var(--dur-fast);
}
.search-input:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); }
.search-clear {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  display: flex; align-items: center; justify-content: center; width: 20px; height: 20px;
  border-radius: 50%; color: var(--text-tertiary); cursor: pointer; background: transparent;
}
.search-clear:hover { background: var(--bg-hover); }
.role-tabs { display: inline-flex; gap: 4px; }
.role-tab {
  padding: 5px 12px; border: 1px solid var(--border); border-radius: var(--radius-md);
  font-size: 12px; color: var(--text-secondary); background: var(--bg-surface); cursor: pointer; transition: all var(--dur-fast);
}
.role-tab:hover { border-color: var(--brand); }
.role-tab.active { background: var(--brand); color: var(--text-on-brand); border-color: var(--brand); }
.icon-btn:disabled { opacity: 0.5; cursor: default; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ---- 用户表 ---- */
.u-avatar {
  width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--brand); color: var(--text-on-brand); font-size: 12px; font-weight: 600;
}
.u-uname { font-weight: 500; color: var(--text-primary); }

.role-badge {
  display: inline-flex; padding: 2px 10px; border-radius: var(--radius-pill);
  font-size: 12px; font-weight: 500;
}
.role-admin { background: var(--danger-soft); color: var(--danger); }
.role-editor { background: var(--accent-blue-soft); color: var(--accent-blue); }
.role-viewer { background: var(--bg-subtle); color: var(--text-secondary); }

.status-badge { display: inline-flex; align-items: center; padding: 2px 10px; border-radius: var(--radius-pill); font-size: 12px; font-weight: 500; }
.status-badge.success { background: var(--success-soft); color: var(--success); }
.status-badge.danger { background: var(--danger-soft); color: var(--danger); }

.row-actions { display: flex; align-items: center; gap: 4px; }
.action-btn {
  display: flex; align-items: center; justify-content: center; width: 28px; height: 28px;
  border-radius: var(--radius-sm); color: var(--text-secondary); background: transparent; cursor: pointer; transition: all var(--dur-fast);
}
.action-btn:hover { background: var(--bg-hover); color: var(--text-primary); }

/* ---- 矩阵 ---- */
.perm-matrix { padding: 18px 20px; }
.mtx { width: 100%; border-collapse: collapse; font-size: 13px; }
.mtx th { text-align: left; padding: 10px 14px; color: var(--text-tertiary); font-weight: 500; border-bottom: 1px solid var(--border); }
.mtx td { padding: 11px 14px; border-bottom: 1px solid var(--border); }
.mtx tr:last-child td { border-bottom: none; }
.mtx-mod { color: var(--text-secondary); }
.sw { display: inline-flex; align-items: center; width: 38px; height: 22px; border-radius: var(--radius-pill); padding: 2px; transition: background var(--dur-fast); }
.sw .knob { width: 18px; height: 18px; border-radius: 50%; background: #fff; transition: transform var(--dur-fast); }
.sw.on { background: var(--brand); }
.sw.on .knob { transform: translateX(16px); }
.sw.off { background: var(--border-strong); }
.sw.off .knob { transform: translateX(0); }
.perm-note { margin: 14px 0 0; font-size: 12px; color: var(--text-tertiary); line-height: 1.6; }

/* ---- 表单 ---- */
.form-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.form-label { width: 76px; flex-shrink: 0; font-size: 13px; color: var(--text-secondary); }
.form-input {
  flex: 1; height: 36px; padding: 0 12px; border: 1px solid var(--border); border-radius: var(--radius-md);
  font-size: 13px; background: var(--bg-surface); color: var(--text-primary); transition: all var(--dur-fast);
}
.form-input:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); }
.form-input:disabled { background: var(--bg-subtle); color: var(--text-tertiary); cursor: not-allowed; }
.seg { display: inline-flex; gap: 4px; }
.seg-btn {
  padding: 6px 14px; border: 1px solid var(--border); border-radius: var(--radius-md);
  font-size: 12px; color: var(--text-secondary); background: var(--bg-surface); cursor: pointer; transition: all var(--dur-fast);
}
.seg-btn:hover { border-color: var(--brand); }
.seg-btn.active { background: var(--brand); color: var(--text-on-brand); border-color: var(--brand); }
.switch { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; }
.switch input { display: none; }
.switch-track {
  width: 38px; height: 22px; border-radius: var(--radius-pill); background: var(--border-strong);
  position: relative; transition: background var(--dur-fast);
}
.switch-knob {
  position: absolute; top: 2px; left: 2px; width: 18px; height: 18px; border-radius: 50%; background: #fff; transition: transform var(--dur-fast);
}
.switch input:checked + .switch-track { background: var(--brand); }
.switch input:checked + .switch-track .switch-knob { transform: translateX(16px); }
.switch-text { font-size: 13px; color: var(--text-secondary); }

@media (max-width: 1040px) {
  .perm-body { grid-template-columns: 1fr; }
}
</style>
