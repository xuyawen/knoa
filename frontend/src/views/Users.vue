<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { createUser, getUserList } from '@/api/auth'
import type { UserOut } from '@/types/api'

const users = ref<UserOut[]>([])
const loading = ref(false)
const error = ref('')

const form = ref({ username: '', password: '', displayName: '', role: 'viewer' })
const submitting = ref(false)
const formError = ref('')

const ROLE_LABEL: Record<string, string> = { admin: '管理员', editor: '编辑', viewer: '访客' }

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

async function onSubmit() {
  formError.value = ''
  if (form.value.username.length < 2) { formError.value = '用户名至少 2 个字符'; return }
  if (form.value.password.length < 6) { formError.value = '密码至少 6 个字符'; return }
  submitting.value = true
  try {
    await createUser({ ...form.value })
    form.value = { username: '', password: '', displayName: '', role: 'viewer' }
    await load()
  } catch (e) {
    formError.value = e instanceof Error ? e.message : '创建失败'
  } finally {
    submitting.value = false
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
          <tr><th>用户名</th><th>显示名</th><th>角色</th><th>状态</th><th>创建时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.username }}</td>
            <td>{{ u.displayName || '—' }}</td>
            <td><span class="role" :class="u.role">{{ ROLE_LABEL[u.role] || u.role }}</span></td>
            <td>{{ u.isActive ? '启用' : '停用' }}</td>
            <td>{{ u.createdAt ? new Date(u.createdAt).toLocaleString() : '—' }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!loading && !error && users.length === 0" class="empty">暂无用户</p>
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
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
}
.tbl th {
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 13px;
}
.role {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
}
.role.admin { background: var(--brand-soft); color: var(--brand); }
.role.editor { background: var(--bg-subtle); color: var(--text-secondary); }
.role.viewer { background: var(--bg-subtle); color: var(--text-secondary); }

.err { color: var(--danger); font-size: 13px; margin: 10px 0 0; }
.empty { color: var(--text-secondary); font-size: 13px; margin: 10px 0 0; }
</style>
