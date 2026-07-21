<script setup lang="ts">
// 权限管理（对应架构图 #7）：真实用户/角色管理 + 后端固定 RBAC 策略参考矩阵。
import { ref, computed, onMounted, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { getUserList, createUser, updateUser, deleteUser } from '@/api/auth'
import type { UserOut, UserCreate, UserUpdate } from '@/types/api'

const auth = useAuthStore()
const toast = useToastStore()

/* ---------- 用户列表 ---------- */
const users = ref<UserOut[]>([])
const loading = ref(false)
const searchQuery = ref('')
const roleFilter = ref<'all' | 'admin' | 'editor' | 'viewer'>('all')
const currentPage = ref(1)
const pageSize = ref(10)

async function loadUsers() {
  loading.value = true
  try {
    users.value = await getUserList()
  } catch (e: any) {
    users.value = []
    toast.error(`加载用户列表失败：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

onMounted(loadUsers)

const filteredUsers = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return users.value.filter((u) => {
    if (roleFilter.value !== 'all' && u.role !== roleFilter.value) return false
    if (!q) return true
    return (
      u.username.toLowerCase().includes(q) ||
      (u.displayName || '').toLowerCase().includes(q)
    )
  })
})

const totalPages = computed(() =>
  Math.max(1, Math.ceil(filteredUsers.value.length / pageSize.value)),
)
const pagedUsers = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredUsers.value.slice(start, start + pageSize.value)
})
function goPage(p: number) {
  if (p >= 1 && p <= totalPages.value) currentPage.value = p
}
function clearSearch() {
  searchQuery.value = ''
}
watch([filteredUsers, pageSize], () => {
  if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
})

/* ---------- 角色样式 ---------- */
function roleClass(r: string) {
  return r === 'admin' ? 'role-admin' : r === 'editor' ? 'role-editor' : 'role-viewer'
}
const ROLE_LABEL: Record<string, string> = { admin: '管理员', editor: '编辑者', viewer: '访客' }

/* ---------- 新建 / 编辑 ---------- */
const showModal = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = ref({ username: '', displayName: '', role: 'viewer', password: '', isActive: true })

function openCreate() {
  editingId.value = null
  form.value = { username: '', displayName: '', role: 'viewer', password: '', isActive: true }
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
async function onDelete(u: UserOut) {
  if (u.id === auth.user?.id) {
    toast.warning('不能删除当前登录账号')
    return
  }
  if (!confirm(`确认删除用户「${u.username}」？该操作不可恢复。`)) return
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
    <header class="page-head">
      <div class="flex items-center">
        <h1 class="page-title">权限管理</h1>
        <span class="sync-flag"><Icon name="shield" :size="12" />同步自后端 RBAC</span>
      </div>
      <p class="page-sub">基于角色的访问控制（RBAC），按用户维度下发权限</p>
    </header>

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
          <button class="icon-btn" title="刷新" :disabled="loading" @click="loadUsers">
            <Icon name="refresh" :size="15" :class="{ spin: loading }" />
          </button>
        </div>

        <div class="user-table-wrap">
          <table class="user-table">
            <thead>
              <tr>
                <th>用户名</th>
                <th>显示名</th>
                <th>角色</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in pagedUsers" :key="u.id">
                <td class="u-name">
                  <span class="u-avatar">{{ (u.displayName || u.username)[0]?.toUpperCase() }}</span>
                  <span class="u-uname">{{ u.username }}</span>
                </td>
                <td class="u-dname">{{ u.displayName || '—' }}</td>
                <td><span class="role-badge" :class="roleClass(u.role)">{{ ROLE_LABEL[u.role] || u.role }}</span></td>
                <td>
                  <span class="status-badge" :class="u.isActive ? 'success' : 'danger'">{{ u.isActive ? '启用' : '停用' }}</span>
                </td>
                <td>
                  <div class="row-actions">
                    <button class="action-btn" title="编辑" @click="openEdit(u)"><Icon name="edit" :size="15" /></button>
                    <button class="action-btn" title="删除" @click="onDelete(u)"><Icon name="trash" :size="15" /></button>
                  </div>
                </td>
              </tr>
              <tr v-if="!loading && !pagedUsers.length">
                <td colspan="5" class="empty-cell">暂无用户（或当前筛选无匹配）</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="pagination-bar" v-if="filteredUsers.length">
          <div class="page-info">共 {{ filteredUsers.length }} 个用户</div>
          <div class="page-numbers">
            <button class="pg" :disabled="currentPage === 1" @click="goPage(currentPage - 1)">&lt;</button>
            <button
              v-for="p in totalPages"
              :key="p"
              class="pg"
              :class="{ active: p === currentPage }"
              @click="goPage(p)"
            >{{ p }}</button>
            <button class="pg" :disabled="currentPage === totalPages" @click="goPage(currentPage + 1)">&gt;</button>
          </div>
        </div>
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
  </div>
</template>

<style scoped>
.page { padding: 20px 24px; }
.flex { display: flex; }
.items-center { align-items: center; }
.page-head { margin-bottom: 18px; }
.page-title { font-size: 18px; font-weight: 700; color: var(--text-primary); margin: 0; }
.sync-flag {
  display: inline-flex; align-items: center; gap: 4px;
  margin-left: 10px; padding: 2px 9px; border-radius: var(--radius-pill);
  font-size: 11px; color: var(--brand); background: var(--brand-soft);
}
.page-sub { margin: 6px 0 0; font-size: 13px; color: var(--text-tertiary); }

.perm-body {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 16px;
  align-items: start;
}
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
.role-tab.active { background: var(--brand); color: #fff; border-color: var(--brand); }
.icon-btn:disabled { opacity: 0.5; cursor: default; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ---- 用户表 ---- */
.user-table-wrap { overflow-x: auto; }
.user-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.user-table th {
  text-align: left; padding: 11px 14px; background: var(--bg-subtle);
  color: var(--text-secondary); font-weight: 600; font-size: 12px;
  border-bottom: 1px solid var(--border); white-space: nowrap;
}
.user-table td { padding: 12px 14px; border-bottom: 1px solid var(--border); vertical-align: middle; }
.user-table tr:last-child td { border-bottom: none; }
.u-name { display: flex; align-items: center; gap: 8px; }
.u-avatar {
  width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--brand); color: #fff; font-size: 12px; font-weight: 600;
}
.u-uname { font-weight: 500; color: var(--text-primary); }
.u-dname { color: var(--text-secondary); }

.role-badge {
  display: inline-flex; padding: 2px 10px; border-radius: var(--radius-pill);
  font-size: 12px; font-weight: 500;
}
.role-admin { background: #FEE2E2; color: #991B1B; }
.role-editor { background: #DBEAFE; color: #1E40AF; }
.role-viewer { background: var(--bg-subtle); color: var(--text-secondary); }

.status-badge { display: inline-flex; align-items: center; padding: 2px 10px; border-radius: var(--radius-pill); font-size: 12px; font-weight: 500; }
.status-badge.success { background: #D1FAE5; color: #065F46; }
.status-badge.danger { background: #FEE2E2; color: #991B1B; }

.row-actions { display: flex; align-items: center; gap: 4px; }
.action-btn {
  display: flex; align-items: center; justify-content: center; width: 28px; height: 28px;
  border-radius: var(--radius-sm); color: var(--text-secondary); background: transparent; cursor: pointer; transition: all var(--dur-fast);
}
.action-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.empty-cell { text-align: center; color: var(--text-tertiary); padding: 32px 0 !important; }

/* ---- 分页 ---- */
.pagination-bar { display: flex; align-items: center; gap: 16px; padding: 12px 4px 2px; font-size: 13px; color: var(--text-secondary); }
.page-info { white-space: nowrap; }
.page-numbers { display: flex; align-items: center; gap: 4px; }
.pg {
  min-width: 30px; height: 30px; display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid var(--border); border-radius: var(--radius-sm); background: transparent;
  font-size: 13px; color: var(--text-secondary); cursor: pointer; padding: 0 8px; font-family: inherit;
}
.pg:hover:not(:disabled) { border-color: var(--brand); color: var(--brand); }
.pg.active { background: var(--brand); color: #fff; border-color: var(--brand); }
.pg:disabled { opacity: 0.4; cursor: default; }

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
.seg-btn.active { background: var(--brand); color: #fff; border-color: var(--brand); }
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
