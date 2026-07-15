<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Icon from './Icon.vue'
import ThemeToggle from './ThemeToggle.vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

defineProps<{ title?: string; subtitle?: string }>()

const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()
const menuOpen = ref(false)
const accountWrap = ref<HTMLElement | null>(null)

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

onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))
</script>

<template>
  <header class="topbar">
    <!-- 左：标题区 -->
    <div class="title-block">
      <h1 class="title">{{ title || '全部知识' }}</h1>
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
            <button class="menu-item danger" @click="onLogout">
              <Icon name="logout" :size="16" />
              <span>退出登录</span>
            </button>
          </div>
        </transition>
      </div>
    </div>
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

@media (max-width: 900px) {
  .topbar {
    display: none;
  }
}
</style>
