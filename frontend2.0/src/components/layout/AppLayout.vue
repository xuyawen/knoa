<script setup lang="ts">
// 应用布局壳：左侧栏（导航）+ 顶栏（品牌/主题/用户）+ 内容区。
// 当前为界面壳，导航项直接从路由 meta 生成；功能接入后可在 meta 加权限控制。
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import Icon from '@/components/ui/Icon.vue'

const theme = useThemeStore()
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const navGroups = [
  {
    title: '',
    items: [
      { to: '/dashboard', title: '首页大盘', icon: 'dashboard' },
      { to: '/documents', title: '文档管理', icon: 'doc' },
      { to: '/search', title: '智能搜索', icon: 'search' },
      { to: '/chat', title: 'AI 智能问答', icon: 'chat' },
      { to: '/graph', title: '知识图谱', icon: 'graph' },
      { to: '/permission', title: '权限管理', icon: 'shield' },
    ],
  },
]

const active = computed(() => route.path)
const user = computed(() => auth.user)
const userInitial = computed(() => user.value?.name?.[0] ?? 'U')
const userRoleLabel = computed(
  () => ({ admin: '管理员', editor: '编辑者', viewer: '访客' })[user.value?.role ?? 'viewer'],
)

const menuOpen = ref(false)
function toggleMenu() {
  menuOpen.value = !menuOpen.value
}
function go(to: string) {
  router.push(to)
  menuOpen.value = false
}
function onLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="layout">
    <!-- 侧栏 -->
    <aside class="sidebar">
      <div class="brand">
        <img src="/favicon.svg" alt="Knoa" class="brand-logo" />
        <div class="brand-text">
          <div class="brand-name">Knoa</div>
          <div class="brand-sub">智能知识库</div>
        </div>
      </div>

      <nav class="nav">
        <template v-for="(g, gi) in navGroups" :key="gi">
          <div v-if="g.title" class="nav-section">{{ g.title }}</div>
          <router-link
            v-for="it in g.items"
            :key="it.to"
            :to="it.to"
            class="nav-item"
            :class="{ active: active === it.to }"
          >
            <Icon :name="it.icon" :size="18" />
            <span>{{ it.title }}</span>
          </router-link>
        </template>
      </nav>

      <div class="sidebar-foot">
        <div class="nav-item" @click="go('/permission')">
          <Icon name="settings" :size="18" />
          <span>系统设置</span>
        </div>
      </div>
    </aside>

    <!-- 主区 -->
    <div class="main">
      <header class="topbar">
        <div class="topbar-title">{{ (route.meta.title as string) || 'Knoa' }}</div>
        <div class="topbar-actions">
          <button class="icon-btn" title="通知">
            <Icon name="bell" :size="18" />
          </button>
          <button class="icon-btn" :title="`主题：${theme.mode}`" @click="theme.cycle()">
            <Icon :name="theme.mode === 'dark' ? 'moon' : theme.mode === 'light' ? 'sun' : 'monitor'" :size="18" />
          </button>

          <div class="user-wrap" @click="toggleMenu">
            <span class="avatar" :style="{ background: user?.avatarColor }">{{ userInitial }}</span>
            <div class="user-meta">
              <span class="user-name">{{ user?.name }}</span>
              <span class="user-role">{{ userRoleLabel }}</span>
            </div>
            <Icon name="chevron" :size="14" class="user-chev" />

            <div v-if="menuOpen" class="user-menu" @click.stop>
              <div class="user-menu-head">
                <span class="avatar lg" :style="{ background: user?.avatarColor }">{{ userInitial }}</span>
                <div>
                  <div class="user-name">{{ user?.name }}</div>
                  <div class="text-xs text-tertiary">{{ user?.dept }}</div>
                </div>
              </div>
              <div class="divider" />
              <div class="menu-item" @click="go('/permission')">
                <Icon name="user" :size="16" /><span>个人中心</span>
              </div>
              <div class="menu-item" @click="go('/permission')">
                <Icon name="settings" :size="16" /><span>账号设置</span>
              </div>
              <div class="divider" />
              <div class="menu-item danger" @click="onLogout">
                <Icon name="logout" :size="16" /><span>退出登录</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <component :is="Component" />
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}

/* 侧栏 */
.sidebar {
  width: var(--sidebar-w);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  padding: 16px 12px;
  position: sticky;
  top: 0;
  height: 100vh;
}
.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 6px 8px 18px;
}
.brand-logo {
  width: 34px;
  height: 34px;
  border-radius: 9px;
}
.brand-name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.01em;
}
.brand-sub {
  font-size: 11px;
  color: var(--text-tertiary);
}
.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  overflow-y: auto;
}
.nav :deep(a.nav-item) {
  text-decoration: none;
}
.sidebar-foot {
  border-top: 1px solid var(--border);
  padding-top: 8px;
  margin-top: 8px;
}

/* 主区 */
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: var(--topbar-h);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: color-mix(in srgb, var(--bg-surface) 88%, transparent);
  backdrop-filter: saturate(180%) blur(12px);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 20;
}
.topbar-title {
  font-size: 15px;
  font-weight: 600;
}
.topbar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.user-wrap {
  position: relative;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 5px 10px 5px 6px;
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition: background var(--dur-fast);
}
.user-wrap:hover {
  background: var(--bg-hover);
}
.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}
.avatar.lg {
  width: 38px;
  height: 38px;
  font-size: 15px;
}
.user-meta {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}
.user-name {
  font-size: 13px;
  font-weight: 600;
}
.user-role {
  font-size: 11px;
  color: var(--text-tertiary);
}
.user-chev {
  color: var(--text-tertiary);
}

/* 用户下拉菜单 */
.user-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 224px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-pop);
  padding: 8px;
  z-index: 50;
  animation: fade-up 0.16s var(--ease-out) both;
}
.user-menu-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px 10px;
}
.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--dur-fast), color var(--dur-fast);
}
.menu-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.menu-item.danger {
  color: var(--danger);
}
.menu-item.danger:hover {
  background: var(--danger-soft);
}

/* 内容 */
.content {
  flex: 1;
  padding: 24px;
  overflow-x: hidden;
}
</style>
