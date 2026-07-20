<script setup lang="ts">
// 个人中心 — 展示当前账户信息 + 修改密码（接 /api/auth/change-password）。
// 设计语言与壳统一：卡片化、token 化配色、亮/暗自适应。
import { computed, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { changePassword } from '@/api/auth'
import Icon from '@/components/ui/Icon.vue'

const auth = useAuthStore()
const toast = useToastStore()

const ROLE_LABEL: Record<string, string> = {
  admin: '管理员',
  editor: '编辑',
  viewer: '访客',
}

const roleLabel = computed(() => ROLE_LABEL[auth.user?.role || 'viewer'] || auth.user?.role || '—')
const displayName = computed(() => auth.user?.displayName || auth.user?.name || '—')
const createdAt = computed(() =>
  auth.user?.createdAt ? new Date(auth.user.createdAt).toLocaleString('zh-CN') : '—',
)

/* ---- 修改密码 ---- */
const pwdOld = ref('')
const pwdNew = ref('')
const pwdConfirm = ref('')
const saving = ref(false)

async function onSubmitPassword() {
  if (!pwdOld.value || !pwdNew.value) {
    toast.error('请填写完整')
    return
  }
  if (pwdNew.value !== pwdConfirm.value) {
    toast.error('两次输入的新密码不一致')
    return
  }
  saving.value = true
  try {
    await changePassword(pwdOld.value, pwdNew.value)
    toast.success('密码修改成功')
    pwdOld.value = pwdNew.value = pwdConfirm.value = ''
  } catch (e) {
    toast.error(e instanceof Error ? e.message : '修改失败，请重试')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="profile">
    <!-- 账户信息 -->
    <section class="prof-card card">
      <div class="card-head">
        <Icon name="user" :size="16" />
        <span>账户信息</span>
      </div>
      <div class="prof-body">
        <div class="prof-row">
          <span class="prof-key">用户名</span>
          <span class="prof-val">{{ auth.user?.username || '—' }}</span>
        </div>
        <div class="prof-row">
          <span class="prof-key">显示名</span>
          <span class="prof-val">{{ displayName }}</span>
        </div>
        <div class="prof-row">
          <span class="prof-key">角色</span>
          <span class="prof-val">
            <span class="role-pill" :class="'role-' + (auth.user?.role || 'viewer')">{{ roleLabel }}</span>
          </span>
        </div>
        <div class="prof-row">
          <span class="prof-key">状态</span>
          <span class="prof-val">
            <span class="status-pill" :class="auth.user?.isActive ? 'on' : 'off'">
              {{ auth.user?.isActive ? '启用' : '停用' }}
            </span>
          </span>
        </div>
        <div class="prof-row">
          <span class="prof-key">创建时间</span>
          <span class="prof-val">{{ createdAt }}</span>
        </div>
      </div>
    </section>

    <!-- 修改密码 -->
    <section class="prof-card card">
      <div class="card-head">
        <Icon name="key" :size="16" />
        <span>修改密码</span>
      </div>
      <form class="pwd-form" @submit.prevent="onSubmitPassword">
        <label class="pwd-field">
          <span class="pwd-label">当前密码</span>
          <input v-model="pwdOld" type="password" autocomplete="current-password" class="pwd-inp" placeholder="请输入当前密码" />
        </label>
        <label class="pwd-field">
          <span class="pwd-label">新密码</span>
          <input v-model="pwdNew" type="password" autocomplete="new-password" class="pwd-inp" placeholder="请输入新密码" />
        </label>
        <label class="pwd-field">
          <span class="pwd-label">确认新密码</span>
          <input v-model="pwdConfirm" type="password" autocomplete="new-password" class="pwd-inp" placeholder="请再次输入新密码" />
        </label>
        <button type="submit" class="pwd-btn" :disabled="saving">
          {{ saving ? '保存中…' : '保存修改' }}
        </button>
      </form>
    </section>
  </div>
</template>

<style scoped>
.profile {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  max-width: 920px;
}
.prof-card {
  padding: 22px;
}
.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 18px;
}
.card-head :deep(svg) { color: var(--brand); }

.prof-body { display: flex; flex-direction: column; gap: 2px; }
.prof-row {
  display: flex;
  align-items: center;
  padding: 12px 4px;
  border-bottom: 1px solid var(--border);
}
.prof-row:last-child { border-bottom: none; }
.prof-key {
  width: 96px;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--text-tertiary);
}
.prof-val { font-size: 14px; color: var(--text-primary); font-weight: 500; }

.role-pill, .status-pill {
  display: inline-block;
  padding: 3px 11px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 600;
}
.role-admin { color: var(--brand); background: var(--brand-soft); }
.role-editor { color: var(--info); background: var(--info-soft); }
.role-viewer { color: var(--text-secondary); background: var(--bg-subtle); }
.status-pill.on { color: var(--success); background: var(--success-soft); }
.status-pill.off { color: var(--danger); background: var(--danger-soft); }

.pwd-form { display: flex; flex-direction: column; gap: 16px; }
.pwd-field { display: flex; flex-direction: column; gap: 6px; }
.pwd-label { font-size: 13px; color: var(--text-secondary); }
.pwd-inp {
  height: 42px;
  padding: 0 14px;
  font-size: 13.5px;
  color: var(--text-primary);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  outline: none;
  transition: border-color var(--dur-fast), box-shadow var(--dur-fast);
  box-sizing: border-box;
}
.pwd-inp:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-ring);
  background: var(--bg-surface);
}
.pwd-btn {
  height: 44px;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, var(--brand), var(--brand-strong, #1d4ed8));
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
  margin-top: 4px;
}
.pwd-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px var(--brand-ring);
}
.pwd-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }

@media (max-width: 760px) {
  .profile { grid-template-columns: 1fr; }
}
</style>
