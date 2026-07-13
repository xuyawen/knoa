<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { createUser, deleteUser, getUserList, updateUser } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import type { UserOut } from '@/types/api'

const auth = useAuthStore()
const users = ref<UserOut[]>([])
const loading = ref(false)
const error = ref('')

const form = ref({ username: '', password: '', displayName: '', role: 'viewer' })
const submitting = ref(false)
const formError = ref('')

// 行内编辑状态
const pwdEditing = ref<string | null>(null)   // 正在重置密码的用户 id
const pwdValue = ref('')
const pwdError = ref('')
const delConfirm = ref<string | null>(null)    // 正在确认删除的用户 id
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

async function onSubmit() {
  formError.value = ''
  if (form.value.username.length < 2) { formError.value = '用户名至少 2 个字符'; return }
  if (form.value.password.length < 6) { formError.value = '密码至少 6 个字符'; return }
  submitting.value = true
  try {
    const u = await createUser({ ...form.value })
    users.value = [...users.value, u]
    form.value = { username: '', password: '', displayName: '', role: 'viewer' }
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
  pwdEditing.value = u.id
  pwdValue.value = ''
  pwdError.value = ''
}

async function confirmPwd(u: UserOut) {
  pwdError.value = ''
  if (pwdValue.value.length < 6) { pwdError.value = '新密码至少 6 个字符'; return }
  rowBusy.value = u.id
  try {
    await updateUser(u.id, { password: pwdValue.value })
    pwdEditing.value = null
    pwdValue.value = ''
  } catch (e) {
    pwdError.value = e instanceof Error ? e.message : '重置密码失败'
  } finally {
    rowBusy.value = null
  }
}

function cancelPwd() {
  pwdEditing.value = null
  pwdValue.value = ''
  pwdError.value = ''
}

async function confirmDel(u: UserOut) {
  rowBusy.value = u.id
  rowError.value = ''
  try {
    await deleteUser(u.id)
    users.value = users.value.filter((x) => x.id !== u.id)
    delConfirm.value = null
  } catch (e) {
    rowError.value = e instanceof Error ? e.message : '删除失败'
  } finally {
    rowBusy.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div>
        <h1>用户管理</h1>
        <p class="sub">管理系统用户与角色（admin 含用户管理 / editor 可建库传文档 / viewer 仅问答）</p>
      </div>
    </header>

    <section class="card">
      <h2>新建用户</h2>
      <form class="create-form" @submit.prevent="onSubmit">
        <input v-model="form.username" placeholder="用户名（≥2）" />
        <input v-model="form.password" type="password" placeholder="密码（≥6）" />
        <input v-model="form.displayName" placeholder="显示名（可选）" />
        <select v-model="form.role">
          <option value="viewer">访客（仅问答）</option>
          <option value="editor">编辑（建库/传文档）</option>
          <option value="admin">管理员（含用户管理）</option>
        </select>
        <button type="submit" :disabled="submitting">{{ submitting ? '创建中…' : '创建用户' }}</button>
      </form>
      <p v-if="formError" class="err">{{ formError }}</p>
    </section>

    <section class="card">
      <h2>用户列表</h2>
      <p v-if="error" class="err">{{ error }}</p>
      <table v-else class="tbl">
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
          <tr v-for="u in users" :key="u.id" :class="{ busy: rowBusy === u.id }">
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

            <!-- 状态：标签 + 切换按钮 -->
            <td>
              <span class="status" :class="u.isActive ? 'on' : 'off'">
                {{ u.isActive ? '启用' : '停用' }}
              </span>
              <button
                class="link-btn"
                :disabled="rowBusy === u.id"
                @click="toggleActive(u)"
              >{{ u.isActive ? '停用' : '启用' }}</button>
            </td>

            <td class="muted">{{ u.createdAt ? new Date(u.createdAt).toLocaleString() : '—' }}</td>

            <!-- 操作列 -->
            <td class="col-ops">
              <!-- 重置密码：行内展开 -->
              <template v-if="pwdEditing === u.id">
                <input
                  v-model="pwdValue"
                  class="pwd-input"
                  type="password"
                  placeholder="新密码（≥6）"
                  @keyup.enter="confirmPwd(u)"
                />
                <button class="mini primary" :disabled="rowBusy === u.id" @click="confirmPwd(u)">确认</button>
                <button class="mini" @click="cancelPwd">取消</button>
              </template>

              <!-- 删除确认：行内展开 -->
              <template v-else-if="delConfirm === u.id">
                <span class="confirm-text">确认删除？</span>
                <button class="mini danger" :disabled="rowBusy === u.id" @click="confirmDel(u)">是</button>
                <button class="mini" @click="delConfirm = null">否</button>
              </template>

              <!-- 默认操作按钮 -->
              <template v-else>
                <button class="link-btn" :disabled="rowBusy === u.id" @click="startPwd(u)">重置密码</button>
                <button
                  class="link-btn danger"
                  :disabled="rowBusy === u.id || auth.user?.id === u.id"
                  :title="auth.user?.id === u.id ? '不能删除自己' : ''"
                  @click="delConfirm = u.id"
                >删除</button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!loading && !error && users.length === 0" class="empty">暂无用户</p>
      <p v-if="rowError" class="err row-err">{{ rowError }}</p>
      <p v-if="pwdError" class="err row-err">{{ pwdError }}</p>
    </section>
  </div>
</template>

<style scoped>
.page {
  height: 100%;
  overflow-y: auto;
  padding: 28px 32px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: var(--bg);
}
.page-head h1 {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 600;
  margin: 0;
}
.sub { margin: 4px 0 0; font-size: 13px; color: var(--text-secondary); }

.card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px 22px;
}
.card h2 {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 14px;
}

.create-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  align-items: end;
}
.create-form input,
.create-form select {
  height: 40px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 14px;
}
.create-form input:focus,
.create-form select:focus {
  outline: none;
  border-color: var(--brand);
}
.create-form button {
  height: 40px;
  padding: 0 18px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--brand);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.create-form button:disabled { opacity: 0.6; cursor: default; }

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

.pwd-input {
  height: 30px;
  width: 130px;
  padding: 0 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 13px;
}
.pwd-input:focus { outline: none; border-color: var(--brand); }
.confirm-text { font-size: 13px; color: var(--danger); margin-right: 4px; }

.err { color: var(--danger); font-size: 13px; margin: 10px 0 0; }
.row-err { margin: 8px 0 0; }
.empty { color: var(--text-secondary); font-size: 13px; margin: 10px 0 0; }
</style>
