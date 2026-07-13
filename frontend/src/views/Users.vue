<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import Icon from '@/components/Icon.vue'
import { useSidebarCollapsed } from '@/composables/useSidebarCollapsed'
import { createUser, deleteUser, getUserList, updateUser } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import type { UserOut } from '@/types/api'

const auth = useAuthStore()
const { collapsed } = useSidebarCollapsed()
function onCollapse() { collapsed.value = true }
function onExpand() { collapsed.value = false }

const users = ref<UserOut[]>([])
const loading = ref(false)
const error = ref('')

// 搜索条件
const keyword = ref('')
const roleFilter = ref<'all' | 'admin' | 'editor' | 'viewer'>('all')
const statusFilter = ref<'all' | 'active' | 'inactive'>('all')

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return users.value.filter((u) => {
    if (roleFilter.value !== 'all' && u.role !== roleFilter.value) return false
    if (statusFilter.value === 'active' && !u.isActive) return false
    if (statusFilter.value === 'inactive' && u.isActive) return false
    if (kw) {
      const hay = `${u.username} ${u.displayName || ''}`.toLowerCase()
      if (!hay.includes(kw)) return false
    }
    return true
  })
})

function resetFilters() {
  keyword.value = ''
  roleFilter.value = 'all'
  statusFilter.value = 'all'
}

const form = ref({ username: '', password: '', displayName: '', role: 'viewer' })
const submitting = ref(false)
const formError = ref('')
const showCreate = ref(false)   // 新建用户弹窗开关

// 成功提示（轻量 toast）
const successMsg = ref('')
let successTimer: ReturnType<typeof setTimeout> | undefined
function scheduleClear() {
  if (successTimer) clearTimeout(successTimer)
  successTimer = setTimeout(() => { successMsg.value = '' }, 3000)
}
function dismissSuccess() {
  successMsg.value = ''
  if (successTimer) clearTimeout(successTimer)
}

// 失败提示（同一套悬浮 toast，红色）
const errorMsg = ref('')
let errorTimer: ReturnType<typeof setTimeout> | undefined
function scheduleErrorClear() {
  if (errorTimer) clearTimeout(errorTimer)
  errorTimer = setTimeout(() => { errorMsg.value = '' }, 3000)
}
function dismissError() {
  errorMsg.value = ''
  if (errorTimer) clearTimeout(errorTimer)
}

// 弹窗状态
const showPwd = ref(false)                       // 重置密码弹窗
const pwdTarget = ref<UserOut | null>(null)      // 正在重置密码的用户
const pwdValue = ref('')
const pwdSubmitting = ref(false)
const pwdError = ref('')
const showDel = ref(false)                       // 删除确认弹窗
const delTarget = ref<UserOut | null>(null)      // 正在删除的用户
const delSubmitting = ref(false)
const delError = ref('')
const rowBusy = ref<string | null>(null)       // 正在请求的行，禁用该行操作
const rowError = ref('')                        // 行级错误提示

const ROLE_LABEL: Record<string, string> = { admin: '管理员', editor: '编辑', viewer: '访客' }
const ROLES = ['admin', 'editor', 'viewer'] as const

async function load() {
  loading.value = true
  error.value = ''
  try {
    users.value = await getUserList()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function patchRow(updated: UserOut) {
  users.value = users.value.map((u) => (u.id === updated.id ? updated : u))
}

function openCreate() {
  form.value = { username: '', password: '', displayName: '', role: 'viewer' }
  formError.value = ''
  showCreate.value = true
}

function closeCreate() {
  if (submitting.value) return
  showCreate.value = false
  form.value = { username: '', password: '', displayName: '', role: 'viewer' }
  formError.value = ''
}

function onKey(e: KeyboardEvent) {
  if (e.key !== 'Escape') return
  if (pwdSubmitting.value || delSubmitting.value || submitting.value) return
  if (showPwd.value) { closePwd(); return }
  if (showDel.value) { closeDel(); return }
  if (showCreate.value) closeCreate()
}

async function onSubmit() {
  formError.value = ''
  if (form.value.username.length < 2) { formError.value = '用户名至少 2 个字符'; return }
  if (form.value.password.length < 6) { formError.value = '密码至少 6 个字符'; return }
  submitting.value = true
  try {
    const u = await createUser({ ...form.value })
    users.value = [...users.value, u]
    successMsg.value = `用户「${u.username}」创建成功`
    submitting.value = false
    closeCreate()
    scheduleClear()
  } catch (e) {
    formError.value = e instanceof Error ? e.message : '创建失败'
  } finally {
    submitting.value = false
  }
}

async function onRoleChange(u: UserOut, role: string) {
  if (u.role === role) return
  rowBusy.value = u.id
  rowError.value = ''
  try {
    patchRow(await updateUser(u.id, { role }))
  } catch (e) {
    rowError.value = e instanceof Error ? e.message : '修改角色失败'
  } finally {
    rowBusy.value = null
  }
}

async function toggleActive(u: UserOut) {
  rowBusy.value = u.id
  rowError.value = ''
  try {
    patchRow(await updateUser(u.id, { isActive: !u.isActive }))
  } catch (e) {
    rowError.value = e instanceof Error ? e.message : '状态切换失败'
  } finally {
    rowBusy.value = null
  }
}

function startPwd(u: UserOut) {
  pwdTarget.value = u
  pwdValue.value = ''
  pwdError.value = ''
  showPwd.value = true
}

function closePwd() {
  if (pwdSubmitting.value) return
  showPwd.value = false
  pwdTarget.value = null
  pwdValue.value = ''
  pwdError.value = ''
}

async function confirmPwd() {
  if (!pwdTarget.value) return
  pwdError.value = ''
  if (pwdValue.value.length < 6) { pwdError.value = '新密码至少 6 个字符'; return }
  pwdSubmitting.value = true
  try {
    await updateUser(pwdTarget.value.id, { password: pwdValue.value })
    closePwd()
  } catch (e) {
    pwdError.value = e instanceof Error ? e.message : '重置密码失败'
  } finally {
    pwdSubmitting.value = false
  }
}

function startDel(u: UserOut) {
  delTarget.value = u
  delError.value = ''
  showDel.value = true
}

function closeDel() {
  if (delSubmitting.value) return
  showDel.value = false
  delTarget.value = null
  delError.value = ''
}

async function confirmDel() {
  if (!delTarget.value) return
  const name = delTarget.value.username
  delSubmitting.value = true
  delError.value = ''
  try {
    await deleteUser(delTarget.value.id)
    users.value = users.value.filter((x) => x.id !== delTarget.value!.id)
    delSubmitting.value = false
    closeDel()
    successMsg.value = `用户「${name}」已删除`
    scheduleClear()
  } catch (e) {
    closeDel()
    errorMsg.value = e instanceof Error ? e.message : '删除失败'
    scheduleErrorClear()
  } finally {
    delSubmitting.value = false
  }
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKey)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  if (successTimer) clearTimeout(successTimer)
  if (errorTimer) clearTimeout(errorTimer)
})
</script>

<template>
  <div class="page">
    <AppSidebar :collapsed="collapsed" @collapse="onCollapse" @expand="onExpand" />
    <div class="main">
      <TopBar title="用户管理" subtitle="管理系统用户与角色" />
      <div class="body">
        <Teleport to="body">
          <transition name="toast">
            <div v-if="successMsg" class="toast" role="status" @click="dismissSuccess">
              {{ successMsg }}
            </div>
          </transition>
        </Teleport>
        <Teleport to="body">
          <transition name="toast">
            <div v-if="errorMsg" class="toast err-toast" role="alert" @click="dismissError">
              {{ errorMsg }}
            </div>
          </transition>
        </Teleport>
        <!-- 操作栏：搜索 + 新建 -->
        <div class="toolbar">
          <form class="search-form" @submit.prevent>
            <span class="sf-icon"><Icon name="search" :size="16" /></span>
            <input
              v-model="keyword"
              class="sf-input"
              type="text"
              placeholder="搜索用户名或显示名"
            />
            <select v-model="roleFilter" class="sf-select">
              <option value="all">全部角色</option>
              <option value="admin">管理员</option>
              <option value="editor">编辑</option>
              <option value="viewer">访客</option>
            </select>
            <select v-model="statusFilter" class="sf-select">
              <option value="all">全部状态</option>
              <option value="active">启用</option>
              <option value="inactive">停用</option>
            </select>
            <button
              v-if="keyword || roleFilter !== 'all' || statusFilter !== 'all'"
              class="sf-reset"
              type="button"
              @click="resetFilters"
            >重置</button>
          </form>
          <button class="add-btn" type="button" @click="openCreate">+ 新建用户</button>
        </div>

        <p v-if="error" class="err">{{ error }}</p>
        <p v-else-if="loading" class="muted">加载中…</p>
        <template v-else>
          <table class="tbl">
            <thead>
              <tr>
                <th>用户名</th>
                <th>显示名</th>
                <th>角色</th>
                <th>状态</th>
                <th>创建时间</th>
                <th class="col-ops">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in filtered" :key="u.id" :class="{ busy: rowBusy === u.id }">
                <td>{{ u.username }}</td>
                <td>{{ u.displayName || '—' }}</td>

                <!-- 角色：下拉直接改 -->
                <td>
                  <select
                    class="role-select"
                    :value="u.role"
                    :disabled="rowBusy === u.id"
                    @change="onRoleChange(u, ($event.target as HTMLSelectElement).value)"
                  >
                    <option v-for="r in ROLES" :key="r" :value="r">{{ ROLE_LABEL[r] }}</option>
                  </select>
                </td>

                <!-- 状态：标签 -->
                <td>
                  <span class="status" :class="u.isActive ? 'on' : 'off'">
                    {{ u.isActive ? '启用' : '停用' }}
                  </span>
                </td>

                <td class="muted">{{ u.createdAt ? new Date(u.createdAt).toLocaleString() : '—' }}</td>

                <!-- 操作列 -->
                <td class="col-ops">
                  <button class="link-btn" :disabled="rowBusy === u.id" @click="startPwd(u)">重置密码</button>
                  <button
                    class="link-btn"
                    :disabled="rowBusy === u.id || auth.user?.id === u.id"
                    :title="auth.user?.id === u.id ? '不能停用自己' : ''"
                    @click="toggleActive(u)"
                  >{{ u.isActive ? '停用' : '启用' }}</button>
                  <button
                    class="link-btn danger"
                    :disabled="rowBusy === u.id || auth.user?.id === u.id"
                    :title="auth.user?.id === u.id ? '不能删除自己' : ''"
                    @click="startDel(u)"
                  >删除</button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="!filtered.length" class="empty">
            {{ users.length ? '没有匹配的用户' : '暂无用户' }}
          </p>
          <p v-if="rowError" class="err row-err">{{ rowError }}</p>
        </template>
      </div>
    </div>

    <!-- 新建用户弹窗 -->
    <Teleport to="body">
      <div v-if="showCreate" class="modal-overlay" @click.self="closeCreate">
        <div class="modal" role="dialog" aria-modal="true" aria-label="新建用户">
          <header class="m-head">
            <h3>新建用户</h3>
            <button class="m-close" type="button" title="关闭" @click="closeCreate">×</button>
          </header>
          <form class="m-body" @submit.prevent="onSubmit">
            <label class="m-field">
              <span>用户名<span class="req">*</span></span>
              <input v-model="form.username" placeholder="至少 2 个字符" />
            </label>
            <label class="m-field">
              <span>密码<span class="req">*</span></span>
              <input v-model="form.password" type="password" placeholder="至少 6 个字符" />
            </label>
            <label class="m-field">
              <span>显示名</span>
              <input v-model="form.displayName" placeholder="可选" />
            </label>
            <label class="m-field">
              <span>角色</span>
              <select v-model="form.role">
                <option value="viewer">访客（仅问答）</option>
                <option value="editor">编辑（建库/传文档）</option>
                <option value="admin">管理员（含用户管理）</option>
              </select>
            </label>
            <p v-if="formError" class="err">{{ formError }}</p>
          </form>
          <footer class="m-foot">
            <button class="mini" type="button" :disabled="submitting" @click="closeCreate">取消</button>
            <button class="mini primary" type="button" :disabled="submitting" @click="onSubmit">
              {{ submitting ? '创建中…' : '保存' }}
            </button>
          </footer>
        </div>
      </div>
    </Teleport>

    <!-- 重置密码弹窗 -->
    <Teleport to="body">
      <div v-if="showPwd" class="modal-overlay" @click.self="closePwd">
        <div class="modal" role="dialog" aria-modal="true" aria-label="重置密码">
          <header class="m-head">
            <h3>重置密码</h3>
            <button class="m-close" type="button" title="关闭" @click="closePwd">×</button>
          </header>
          <form class="m-body" @submit.prevent="confirmPwd">
            <p class="m-desc">为用户 <strong>{{ pwdTarget?.username }}</strong> 设置新密码</p>
            <label class="m-field">
              <span>新密码<span class="req">*</span></span>
              <input v-model="pwdValue" type="password" placeholder="至少 6 个字符" />
            </label>
            <p v-if="pwdError" class="err">{{ pwdError }}</p>
          </form>
          <footer class="m-foot">
            <button class="mini" type="button" :disabled="pwdSubmitting" @click="closePwd">取消</button>
            <button class="mini primary" type="button" :disabled="pwdSubmitting" @click="confirmPwd">
              {{ pwdSubmitting ? '提交中…' : '确认' }}
            </button>
          </footer>
        </div>
      </div>
    </Teleport>

    <!-- 删除确认弹窗 -->
    <Teleport to="body">
      <div v-if="showDel" class="modal-overlay" @click.self="closeDel">
        <div class="modal" role="dialog" aria-modal="true" aria-label="删除用户">
          <header class="m-head">
            <h3>删除用户</h3>
            <button class="m-close" type="button" title="关闭" @click="closeDel">×</button>
          </header>
          <div class="m-body">
            <p class="m-warn">
              此操作不可恢复，将永久删除用户 <strong>{{ delTarget?.username }}</strong> 及其所有权限记录。
            </p>
          </div>
          <footer class="m-foot">
            <button class="mini" type="button" :disabled="delSubmitting" @click="closeDel">取消</button>
            <button class="mini danger" type="button" :disabled="delSubmitting" @click="confirmDel">
              {{ delSubmitting ? '删除中…' : '确认删除' }}
            </button>
          </footer>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  height: 100%;
  overflow-x: hidden;
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 操作栏：搜索 + 新建 */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.search-form {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.sf-icon {
  display: flex;
  color: var(--text-secondary);
}
.sf-input {
  height: 40px;
  width: 240px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 14px;
}
.sf-select {
  height: 40px;
  padding: 0 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
}
.sf-input:focus,
.sf-select:focus {
  outline: none;
  border-color: var(--brand);
}
.sf-reset {
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease;
}
.sf-reset:hover {
  color: var(--text-primary);
  border-color: var(--brand);
}
.add-btn {
  flex-shrink: 0;
  height: 40px;
  padding: 0 18px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--brand);
  color: #fff;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: opacity 0.15s ease;
}
.add-btn:hover { opacity: 0.9; }

.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.tbl th, .tbl td {
  text-align: left;
  padding: 11px 12px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
.tbl th {
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 13px;
}
.tbl tr.busy { opacity: 0.6; }
.muted { color: var(--text-secondary); font-size: 13px; }
.col-ops { white-space: nowrap; }

/* 角色下拉 */
.role-select {
  height: 30px;
  padding: 0 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
}
.role-select:focus { outline: none; border-color: var(--brand); }
.role-select:disabled { cursor: default; }

/* 状态标签 */
.status {
  display: inline-block;
  padding: 2px 9px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  margin-right: 8px;
}
.status.on { background: rgba(34, 197, 94, 0.16); color: #22c55e; }
.status.off { background: var(--bg-subtle); color: var(--text-secondary); }

/* 文字按钮 */
.link-btn {
  background: none;
  border: none;
  color: var(--brand);
  font-size: 13px;
  cursor: pointer;
  padding: 2px 4px;
  transition: opacity 0.15s ease;
}
.link-btn:hover:not(:disabled) { opacity: 0.75; }
.link-btn:disabled { color: var(--text-secondary); opacity: 0.5; cursor: default; }
.link-btn.danger { color: var(--danger); }

/* 迷你按钮（确认/取消） */
.mini {
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  margin-left: 6px;
}
.mini.primary { background: var(--brand); color: #fff; border-color: var(--brand); }
.mini.danger { background: var(--danger); color: #fff; border-color: var(--danger); }
.mini:disabled { opacity: 0.6; cursor: default; }

.m-desc { font-size: 14px; color: var(--text-secondary); margin: 0; }
.m-desc strong { color: var(--text-primary); }
.m-warn {
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
  color: var(--text-primary);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
  padding: 12px 14px;
}
.m-warn strong { color: var(--danger); }

.err { color: var(--danger); font-size: 13px; margin: 0; }
.row-err { margin: 8px 0 0; }
.empty { color: var(--text-secondary); font-size: 13px; margin: 10px 0 0; }

/* 成功提示 toast（悬浮，fixed 顶部居中） */
.toast {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 90;
  display: inline-flex;
  align-items: center;
  padding: 12px 20px;
  border-radius: var(--radius-md);
  background: rgba(34, 197, 94, 0.16);
  border: 1px solid rgba(34, 197, 94, 0.45);
  color: #22c55e;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: var(--shadow-float);
  animation: toast-in 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-enter-active,
.toast-leave-active { transition: opacity 0.2s ease; }
.toast-enter-from,
.toast-leave-to { opacity: 0; }
@keyframes toast-in { from { opacity: 0; } to { opacity: 1; } }

/* 失败提示 toast：同款悬浮，红色 */
.toast.err-toast {
  background: rgba(239, 68, 68, 0.16);
  border: 1px solid rgba(239, 68, 68, 0.45);
  color: #ef4444;
}

/* 新建用户弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(2px);
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: m-fade 0.18s ease;
}
.modal {
  width: min(440px, 92vw);
  max-height: 90vh;
  overflow-y: auto;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-float);
  animation: m-pop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.m-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
}
.m-head h3 {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 600;
  margin: 0;
}
.m-close {
  width: 30px;
  height: 30px;
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background 0.15s ease;
}
.m-close:hover { background: var(--bg-subtle); }
.m-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px;
}
.m-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.m-field span {
  font-size: 13px;
  color: var(--text-secondary);
}
.req { color: var(--danger); margin-left: 2px; }
.m-field input,
.m-field select {
  height: 40px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 14px;
}
.m-field input:focus,
.m-field select:focus {
  outline: none;
  border-color: var(--brand);
}
.m-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
}

@keyframes m-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes m-pop {
  from { opacity: 0; transform: translateY(8px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
</style>
