<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import Icon from '@/components/Icon.vue'
import { useSidebarCollapsed } from '@/composables/useSidebarCollapsed'
import { createUser, deleteUser, getUserList, updateUser } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import type { UserOut } from '@/types/api'

const auth = useAuthStore()
const { collapsed } = useSidebarCollapsed()
const router = useRouter()
const toast = useToast()
function onCollapse() { collapsed.value = true }
function onExpand() { collapsed.value = false }

const isMobile = ref(false)
const drawer = ref(false)
let mq: MediaQueryList | undefined

function syncMobile() {
  isMobile.value = window.matchMedia('(max-width: 900px)').matches
}

const users = ref<UserOut[]>([])
const loading = ref(false)
const error = ref('')

// 搜索条件
const keyword = ref('')
const roleFilter = ref<'all' | 'admin' | 'editor' | 'viewer'>('all')
const statusFilter = ref<'all' | 'active' | 'inactive'>('all')
const roleOpen = ref(false)
const statusOpen = ref(false)
const roleOpenRow = ref<string | null>(null)   // 表格行内角色下拉：存 user.id
const modalRoleOpen = ref(false)               // 编辑弹窗角色下拉

const ROLE_OPTIONS: Record<string, string> = { all: '全部角色', admin: '管理员', editor: '编辑', viewer: '访客' }
const STATUS_OPTIONS: Record<string, string> = { all: '全部状态', active: '启用', inactive: '停用' }

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
const showCreate = ref(false)   // 新建用户弹窗开关

// 弹窗状态
const showPwd = ref(false)                       // 重置密码弹窗
const pwdTarget = ref<UserOut | null>(null)      // 正在重置密码的用户
const pwdValue = ref('')
const pwdSubmitting = ref(false)
const showDel = ref(false)                       // 删除确认弹窗
const delTarget = ref<UserOut | null>(null)      // 正在删除的用户
const delSubmitting = ref(false)
const delError = ref('')
const rowBusy = ref<string | null>(null)       // 正在请求的行，禁用该行操作

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
  showCreate.value = true
}

function closeCreate() {
  if (submitting.value) return
  showCreate.value = false
  form.value = { username: '', password: '', displayName: '', role: 'viewer' }
}

function onKey(e: KeyboardEvent) {
  if (e.key !== 'Escape') return
  if (pwdSubmitting.value || delSubmitting.value || submitting.value) return
  if (showPwd.value) { closePwd(); return }
  if (showDel.value) { closeDel(); return }
  if (showCreate.value) closeCreate()
}

async function onSubmit() {
  if (form.value.username.length < 2) { toast.error('用户名至少 2 个字符'); return }
  if (form.value.password.length < 6) { toast.error('密码至少 6 个字符'); return }
  submitting.value = true
  try {
    const u = await createUser({ ...form.value })
    users.value = [...users.value, u]
    closeCreate()
    toast.success(`用户「${u.username}」创建成功`)
  } catch (e) {
    toast.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

async function onRoleChange(u: UserOut, role: string) {
  if (u.role === role) return
  rowBusy.value = u.id
  try {
    patchRow(await updateUser(u.id, { role }))
  } catch (e) {
    toast.error(e instanceof Error ? e.message : '修改角色失败')
  } finally {
    rowBusy.value = null
  }
}

async function toggleActive(u: UserOut) {
  rowBusy.value = u.id
  try {
    patchRow(await updateUser(u.id, { isActive: !u.isActive }))
  } catch (e) {
    toast.error(e instanceof Error ? e.message : '状态切换失败')
  } finally {
    rowBusy.value = null
  }
}

function startPwd(u: UserOut) {
  pwdTarget.value = u
  pwdValue.value = ''
  showPwd.value = true
}

function closePwd() {
  if (pwdSubmitting.value) return
  showPwd.value = false
  pwdTarget.value = null
  pwdValue.value = ''
}

async function confirmPwd() {
  if (!pwdTarget.value) return
  if (pwdValue.value.length < 6) { toast.error('新密码至少 6 个字符'); return }
  pwdSubmitting.value = true
  try {
    await updateUser(pwdTarget.value.id, { password: pwdValue.value })
    closePwd()
  } catch (e) {
    toast.error(e instanceof Error ? e.message : '重置密码失败')
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
  try {
    await deleteUser(delTarget.value.id)
    users.value = users.value.filter((x) => x.id !== delTarget.value!.id)
    closeDel()
    toast.success(`用户「${name}」已删除`)
  } catch (e) {
    closeDel()
    toast.error(e instanceof Error ? e.message : '删除失败')
  } finally {
    delSubmitting.value = false
  }
}

onMounted(() => {
  syncMobile()
  mq = window.matchMedia('(max-width: 900px)')
  mq.addEventListener('change', syncMobile)
  load()
  window.addEventListener('keydown', onKey)
  // 点击外部关闭下拉
  document.addEventListener('click', (e: MouseEvent) => {
    const t = e.target as HTMLElement
    if (!t.closest('.sf-dropdown')) {
      roleOpen.value = false
      statusOpen.value = false
    }
    if (!t.closest('.row-dropdown')) {
      roleOpenRow.value = null
    }
    if (!t.closest('.modal-dropdown')) {
      modalRoleOpen.value = false
    }
  })
})
onUnmounted(() => {
  mq?.removeEventListener('change', syncMobile)
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div class="page">
    <AppSidebar :collapsed="collapsed" :mobile-open="drawer" @collapse="onCollapse" @expand="onExpand" @close="drawer = false" />
    <div v-if="isMobile && drawer" class="overlay" @click="drawer = false" />

    <!-- 移动端顶栏 -->
    <header v-if="isMobile" class="m-top">
      <button class="m-menu" @click="drawer = true" title="菜单">
        <Icon name="menu" :size="20" />
      </button>
      <span class="m-title">用户管理</span>
      <button class="m-back" @click="router.push('/')">返回</button>
    </header>

    <div class="main">
      <TopBar v-if="!isMobile" title="用户管理" subtitle="管理系统用户与角色" />
      <div class="body">
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
            <div class="sf-dropdown" :class="{ open: roleOpen }">
              <button type="button" class="sf-trigger" @click="roleOpen = !roleOpen">
                <span>{{ ROLE_OPTIONS[roleFilter] }}</span>
                <Icon name="chevron-down" :size="14" />
              </button>
              <transition name="dropdown">
                <ul v-if="roleOpen" class="sf-menu">
                  <li v-for="(label, val) in ROLE_OPTIONS" :key="val"
                    :class="{ active: roleFilter === val }"
                    @click="roleFilter = (val as typeof roleFilter.value); roleOpen = false">{{ label }}</li>
                </ul>
              </transition>
            </div>
            <div class="sf-dropdown" :class="{ open: statusOpen }">
              <button type="button" class="sf-trigger" @click="statusOpen = !statusOpen">
                <span>{{ STATUS_OPTIONS[statusFilter] }}</span>
                <Icon name="chevron-down" :size="14" />
              </button>
              <transition name="dropdown">
                <ul v-if="statusOpen" class="sf-menu">
                  <li v-for="(label, val) in STATUS_OPTIONS" :key="val"
                    :class="{ active: statusFilter === val }"
                    @click="statusFilter = (val as typeof statusFilter.value); statusOpen = false">{{ label }}</li>
                </ul>
              </transition>
            </div>
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
          <!-- 桌面端：表格 -->
          <table v-if="!isMobile" class="tbl">
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

                <!-- 角色：自定义下拉 -->
                <td>
                  <div class="row-dropdown" :class="{ open: roleOpenRow === u.id }">
                    <button type="button" class="row-trigger"
                      :disabled="rowBusy === u.id"
                      @click="roleOpenRow = roleOpenRow === u.id ? null : u.id"
                    >
                      <span>{{ ROLE_LABEL[u.role] || u.role }}</span>
                      <Icon name="chevron-down" :size="12" />
                    </button>
                    <transition name="dropdown">
                      <ul v-if="roleOpenRow === u.id" class="row-menu">
                        <li v-for="r in ROLES" :key="r"
                          :class="{ active: u.role === r }"
                          @click="onRoleChange(u, r); roleOpenRow = null"
                        >{{ ROLE_LABEL[r] }}</li>
                      </ul>
                    </transition>
                  </div>
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

          <!-- 移动端：卡片列表 -->
          <div v-else class="m-user-list">
            <div
              v-for="u in filtered"
              :key="u.id"
              class="m-user-card"
              :class="{ busy: rowBusy === u.id }"
            >
              <div class="m-card-head">
                <span class="m-card-name">{{ u.displayName || u.username }}</span>
                <span class="status" :class="u.isActive ? 'on' : 'off'">
                  {{ u.isActive ? '启用' : '停用' }}
                </span>
              </div>
              <div class="m-card-sub">{{ u.username }} · {{ ROLE_LABEL[u.role] || u.role }}</div>
              <div class="m-card-time muted">{{ u.createdAt ? new Date(u.createdAt).toLocaleString() : '—' }}</div>
              <div class="m-card-actions">
                <button class="link-btn" :disabled="rowBusy === u.id" @click="startPwd(u)">重置密码</button>
                <button
                  class="link-btn"
                  :disabled="rowBusy === u.id || auth.user?.id === u.id"
                  @click="toggleActive(u)"
                >{{ u.isActive ? '停用' : '启用' }}</button>
                <button
                  class="link-btn danger"
                  :disabled="rowBusy === u.id || auth.user?.id === u.id"
                  @click="startDel(u)"
                >删除</button>
              </div>
            </div>
          </div>

          <p v-if="!filtered.length" class="empty">
            {{ users.length ? '没有匹配的用户' : '暂无用户' }}
          </p>
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
              <div class="modal-dropdown" :class="{ open: modalRoleOpen }">
                <button type="button" class="modal-trigger" @click="modalRoleOpen = !modalRoleOpen">
                  <span>{{ ROLE_LABEL[form.role] || form.role }}</span>
                  <Icon name="chevron-down" :size="14" />
                </button>
                <transition name="dropdown">
                  <ul v-if="modalRoleOpen" class="modal-menu">
                    <li v-for="(label, val) in ({ viewer: '访客（仅问答）', editor: '编辑（建库/传文档）', admin: '管理员（含用户管理）' })" :key="val"
                      :class="{ active: form.role === val }"
                      @click="form.role = val as 'viewer'|'editor'|'admin'; modalRoleOpen = false"
                    >{{ label }}</li>
                  </ul>
                </transition>
              </div>
            </label>
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
/* 自定义下拉筛选器 */
.sf-dropdown {
  position: relative;
}
.sf-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 13.5px;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.sf-trigger:hover {
  border-color: var(--brand);
}
.sf-dropdown.open .sf-trigger {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(59,130,246,0.12);
}
.sf-trigger .icon {
  color: var(--text-secondary);
  transition: transform 0.2s ease;
}
.sf-dropdown.open .sf-trigger .icon {
  transform: rotate(180deg);
}
.sf-menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 100%;
  padding: 4px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-float);
  z-index: 10;
  list-style: none;
}
.sf-menu li {
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-size: 13.5px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.1s ease;
}
.sf-menu li:hover {
  background: var(--brand-soft);
}
.sf-menu li.active {
  color: var(--brand);
  font-weight: 500;
}
.sf-input:focus {
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
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: var(--btn-padding-md);
  border: none;
  border-radius: var(--radius-md);
  background: var(--brand);
  color: #fff;
  font-weight: var(--btn-font-weight);
  font-size: var(--btn-font-size);
  cursor: pointer;
  transition: background 0.15s ease;
}
.add-btn:hover { background: var(--brand-hover); }

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

/* 表格行内角色下拉 */
.row-dropdown {
  position: relative;
  display: inline-flex;
  align-items: center;
}
.row-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.row-trigger:hover:not(:disabled) {
  border-color: var(--brand);
}
.row-dropdown.open .row-trigger {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(59,130,246,0.12);
}
.row-dropdown.open .row-trigger svg {
  transform: rotate(180deg);
}
.row-trigger svg { transition: transform 0.2s; flex-shrink: 0; }
.row-trigger:disabled { cursor: default; opacity: 0.55; }
.row-menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 20;
  min-width: 100px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 16px rgba(0,0,0,0.10);
  padding: 4px 0;
  list-style: none;
}
.row-menu li {
  padding: 6px 14px;
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}
.row-menu li:hover { background: var(--bg-subtle); }
.row-menu li.active {
  color: var(--brand);
  font-weight: 600;
}

/* 编辑弹窗角色下拉 */
.modal-dropdown {
  position: relative;
}
.modal-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 38px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.modal-trigger:hover { border-color: var(--brand); }
.modal-dropdown.open .modal-trigger {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(59,130,246,0.12);
}
.modal-dropdown.open .modal-trigger svg { transform: rotate(180deg); }
.modal-trigger svg { transition: transform 0.2s; flex-shrink: 0; }
.modal-menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 30;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 16px rgba(0,0,0,0.10);
  padding: 4px 0;
  list-style: none;
}
.modal-menu li {
  padding: 8px 16px;
  font-size: 14px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}
.modal-menu li:hover { background: var(--bg-subtle); }
.modal-menu li.active {
  color: var(--brand);
  font-weight: 600;
}

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
.empty { color: var(--text-secondary); font-size: 13px; margin: 10px 0 0; }

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
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-float);
  animation: m-pop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
}
.m-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
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
  overflow-y: auto;
  min-height: 0;
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
.m-field input {
  height: 40px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 14px;
}
.m-field input:focus {
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

@media (max-width: 900px) {
  .main {
    padding-top: var(--mobile-topbar-h);
  }
  .body {
    padding: 12px;
  }
  .toolbar {
    flex-direction: column; align-items: stretch;
  }
  .search-form {
    flex-wrap: wrap;
  }
  .sf-input { width: 100%; }
  .tbl { display: none; }
}

/* 移动端用户卡片 */
.m-user-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-user-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
}
.m-user-card.busy { opacity: 0.6; }
.m-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.m-card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.m-card-sub {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 2px;
}
.m-card-time {
  font-size: 12px;
  margin-bottom: 10px;
}
.m-card-actions {
  display: flex;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}

/* 移动端顶栏 */
.m-top {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: var(--mobile-topbar-h);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  z-index: 30;
}
.m-menu {
  width: 36px; height: 36px;
  border-radius: var(--radius-pill);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-primary);
}
.m-title {
  font-family: var(--font-display); font-size: 16px; font-weight: 600;
}
.m-back {
  margin-left: auto;
  font-size: 13px; color: var(--brand); font-weight: 500;
  background: none; border: none;
  cursor: pointer;
}
.overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 35;
}

/* 下拉过渡 */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
