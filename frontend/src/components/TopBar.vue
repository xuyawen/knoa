<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Icon from './Icon.vue'
import ThemeToggle from './ThemeToggle.vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { changePassword } from '@/api/auth'

defineProps<{ title?: string; subtitle?: string }>()

const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()
const menuOpen = ref(false)
const accountWrap = ref<HTMLElement | null>(null)

// 修改密码弹窗
const pwdDialogOpen = ref(false)
const pwdOld = ref('')
const pwdNew = ref('')
const pwdConfirm = ref('')
const pwdSaving = ref(false)
const pwdMsg = ref('') // '' | 'success' | error text
const pwdError = ref(false)

const ROLE_LABEL: Record<string, string> = { admin: '管理员', editor: '编辑', viewer: '访客' }

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function onDocClick(e: MouseEvent) {
  const el = accountWrap.value
  if (!el || el.contains(e.target as Node)) return
  menuOpen.value = false
}

function onLogout() {
  auth.logout()
  menuOpen.value = false
  router.replace('/login')
}

function openPwdDialog() {
  pwdOld.value = ''
  pwdNew.value = ''
  pwdConfirm.value = ''
  pwdMsg.value = ''
  pwdError.value = false
  pwdDialogOpen.value = true
  menuOpen.value = false
}

function closePwdDialog() {
  if (pwdSaving.value) return
  pwdDialogOpen.value = false
}

async function onSubmitPassword() {
  pwdMsg.value = ''
  pwdError.value = false

  if (!pwdOld.value || !pwdNew.value || !pwdConfirm.value) {
    pwdMsg.value = '请填写所有字段'
    pwdError.value = true
    return
  }
  if (pwdNew.value.length < 6) {
    pwdMsg.value = '新密码至少 6 位'
    pwdError.value = true
    return
  }
  if (pwdNew.value !== pwdConfirm.value) {
    pwdMsg.value = '两次输入的新密码不一致'
    pwdError.value = true
    return
  }

  pwdSaving.value = true
  try {
    await changePassword(pwdOld.value, pwdNew.value)
    pwdMsg.value = '密码修改成功'
    setTimeout(() => {
      closePwdDialog()
    }, 1500)
  } catch (e: any) {
    pwdMsg.value = e.message || '修改失败，请重试'
    pwdError.value = true
  } finally {
    pwdSaving.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))
</script>

<template>
  <header class="topbar">
    <!-- 左：标题区 -->
    <div class="title-block">
      <h1 v-if="title" class="title">{{ title }}</h1>
      <span class="subtitle">{{ subtitle || '运营知识一站式问答' }}</span>
    </div>

    <!-- 中：全局命令面板触发器 -->
    <button class="search" @click="ui.openPalette()">
      <span class="search-icon"><Icon name="search" :size="16" /></span>
      <span class="search-placeholder">向知海提问，⌘K 唤起</span>
      <kbd class="kbd">⌘K</kbd>
    </button>

    <!-- 右：操作区 -->
    <div class="actions">
      <slot name="actions-extra" />
      <ThemeToggle />
      <div class="account-wrap" ref="accountWrap">
        <button class="account" @click.stop="toggleMenu" :title="auth.user?.displayName || auth.user?.username">
          {{ (auth.user?.displayName || auth.user?.username || '?').charAt(0) }}
        </button>
        <transition name="menu-fade">
          <div v-if="menuOpen" class="account-menu">
            <div class="menu-header">
              <span class="menu-name">{{ auth.user?.displayName || auth.user?.username }}</span>
              <span class="menu-role">{{ ROLE_LABEL[auth.user?.role || ''] || auth.user?.role }}</span>
            </div>
            <div class="menu-divider" />
            <button class="menu-item" @click="openPwdDialog">
              <Icon name="key" :size="16" />
              <span>修改密码</span>
            </button>
            <button class="menu-item danger" @click="onLogout">
              <Icon name="logout" :size="16" />
              <span>退出登录</span>
            </button>
          </div>
        </transition>
      </div>
    </div>

    <!-- 修改密码弹窗 -->
    <teleport to="body">
      <transition name="fade">
        <div v-if="pwdDialogOpen" class="pwd-overlay" @click.self="closePwdDialog">
          <div class="pwd-dialog">
            <div class="pwd-header">
              <h3>修改密码</h3>
              <button class="pwd-close" @click="closePwdDialog">&times;</button>
            </div>
            <form @submit.prevent="onSubmitPassword" class="pwd-form">
              <label class="pwd-field">
                <span>原密码</span>
                <input
                  type="password"
                  v-model="pwdOld"
                  placeholder="输入当前密码"
                  autocomplete="current-password"
                  :disabled="pwdSaving"
                />
              </label>
              <label class="pwd-field">
                <span>新密码</span>
                <input
                  type="password"
                  v-model="pwdNew"
                  placeholder="至少 6 位"
                  autocomplete="new-password"
                  :disabled="pwdSaving"
                />
              </label>
              <label class="pwd-field">
                <span>确认新密码</span>
                <input
                  type="password"
                  v-model="pwdConfirm"
                  placeholder="再次输入新密码"
                  autocomplete="new-password"
                  :disabled="pwdSaving"
                />
              </label>
              <p v-if="pwdMsg" class="pwd-msg" :class="{ error: pwdError, success: !pwdError }">{{ pwdMsg }}</p>
              <div class="pwd-actions">
                <button type="button" class="pwd-btn cancel" @click="closePwdDialog" :disabled="pwdSaving">取消</button>
                <button type="submit" class="pwd-btn submit" :disabled="pwdSaving">
                  {{ pwdSaving ? '提交中…' : '确认修改' }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </transition>
    </teleport>
  </header>
</template>

<style scoped>
.topbar {
  height: var(--topbar-h);
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 24px;
  padding: 0 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
  flex-shrink: 0;
}
.title-block {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  min-width: 0;
  justify-self: start;
}
.title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  white-space: nowrap;
}
.subtitle {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.search {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 480px;
  max-width: 100%;
  height: 38px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  background: var(--bg-subtle);
  color: var(--text-placeholder);
  font-size: 13px;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.search:hover {
  border-color: var(--brand);
}
.search-icon {
  display: flex;
  color: var(--text-secondary);
}
.search-placeholder {
  flex: 1;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.kbd {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-family: var(--font-sans);
}
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-self: end;
}
.icon-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.icon-btn:hover {
  background: var(--brand-soft);
  color: var(--brand);
  border-color: transparent;
}
.account {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-pill);
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 13px;
  transition: opacity 0.15s ease;
}
.account:hover {
  opacity: 0.85;
}
.account-wrap {
  position: relative;
}
.account-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 200px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-float);
  padding: 8px;
  z-index: 50;
}
.menu-header {
  padding: 8px 10px 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.menu-name {
  font-size: 14px;
  font-weight: 500;
}
.menu-role {
  font-size: 12px;
  color: var(--text-secondary);
}
.menu-divider {
  height: 1px;
  background: var(--border);
  margin: 6px 0;
}
.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-primary);
  transition: background 0.15s ease;
}
.menu-item:hover {
  background: var(--bg-subtle);
}
.menu-item.danger {
  color: var(--danger);
}
.menu-item.danger:hover {
  background: var(--danger-soft);
}
.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.12s ease, transform 0.12s ease;
}
.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ── 修改密码弹窗 ── */
.pwd-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.pwd-dialog {
  width: 380px;
  max-width: 90vw;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-float);
  padding: 24px;
}
.pwd-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.pwd-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}
.pwd-close {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 18px;
  cursor: pointer;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pwd-close:hover { background: var(--bg-subtle); }
.pwd-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.pwd-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 13px;
  color: var(--text-secondary);
}
.pwd-field input {
  height: 38px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-page);
  color: var(--text-primary);
  padding: 0 12px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s ease;
}
.pwd-field input:focus { border-color: var(--brand); }
.pwd-field input:disabled { opacity: 0.6; }
.pwd-msg {
  font-size: 13px;
  margin: -4px 0 0;
  min-height: 20px;
}
.pwd-msg.error { color: var(--danger); }
.pwd-msg.success { color: var(--success, #22c55e); }
.pwd-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}
.pwd-btn {
  height: 34px;
  padding: 0 18px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.pwd-btn.cancel {
  background: transparent;
  color: var(--text-primary);
}
.pwd-btn.cancel:hover { background: var(--bg-subtle); }
.pwd-btn.submit {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.pwd-btn.submit:hover:not(:disabled) { opacity: 0.9; }
.pwd-btn:disabled { opacity: 0.55; cursor: not-allowed; }

/* 弹窗淡入 */
.fade-enter-active,
.fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from,
.fade-leave-to { opacity: 0; }

@media (max-width: 900px) {
  .topbar {
    display: none;
  }
}
</style>
