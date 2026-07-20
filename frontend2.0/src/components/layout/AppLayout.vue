<script setup lang="ts">
// 布局壳：顶部水平导航栏（logo+主导航+用户）+ 左侧页面子菜单 + 右侧主内容。
// 按 6 张目标 UI 截图 1:1 还原。
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Icon from '@/components/ui/Icon.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

/* ---------- 顶部主导航 ---------- */
const topNavItems = [
  { to: '/dashboard', label: '首页大盘' },
  { to: '/documents', label: '文档管理' },
  { to: '/search', label: '智能搜索' },
  { to: '/chat', label: 'AI智能问答' },
  { to: '/graph', label: '知识图谱' },
  { to: '/profile', label: '个人中心' },
  { to: '/permission', label: '系统管理' },
]

/* ---------- 左侧子菜单（按路由切换）---------- */
interface SubItem { label: string; icon?: string; active?: boolean }

const subMenus: Record<string, SubItem[]> = {
  dashboard: [
    { label: '数据总览', icon: 'grid', active: true },
    { label: '访问分析', icon: 'chart' },
    { label: '文档统计', icon: 'doc' },
    { label: '用户统计', icon: 'users' },
    { label: '热门内容', icon: 'fire' },
    { label: '系统公告', icon: 'bell' },
  ],
  documents: [
    { label: '我的文档', icon: 'folder', active: true },
    { label: '公共文档', icon: 'globe' },
    { label: '部门文档', icon: 'team' },
    { label: '文档归档', icon: 'archive' },
  ],
  search: [
    { label: '搜索历史', icon: 'clock', active: true },
    { label: '热门搜索', icon: 'fire' },
    { label: '搜索筛选', icon: 'filter' },
  ],
  chat: [
    { label: '新建对话', icon: 'plus', active: true },
    { label: '历史会话', icon: 'history' },
    { label: '问答记录', icon: 'list' },
    { label: '模型配置', icon: 'settings' },
  ],
  graph: [
    { label: '全局图谱', icon: 'graph', active: true },
    { label: '节点管理', icon: 'node' },
    { label: '关系检索', icon: 'link' },
    { label: '图谱统计', icon: 'chart' },
  ],
}

const currentSubItems = computed<SubItem[]>(() => {
  const p = route.path.replace(/^\//, '').split('/')[0]
  return subMenus[p] ?? []
})

const activeSub = ref(0)
// 当路由切换时，重置到第一个 active 项
import { watch } from 'vue'
watch(() => route.path, () => {
  const idx = currentSubItems.value.findIndex(i => i.active)
  activeSub.value = idx >= 0 ? idx : 0
}, { immediate: true })

/* ---------- 用户下拉 ---------- */
const userMenuOpen = ref(false)
function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value
}
function closeUserMenu() {
  userMenuOpen.value = false
}
function onLogout() {
  auth.logout()
  router.push('/login')
}

const user = computed(() => auth.user)
const userInitial = computed(() => user.value?.name?.[0] ?? '管')
</script>

<template>
  <div class="layout" @click.self="closeUserMenu">
    <!-- ====== 顶部水平导航栏 ====== -->
    <header class="topbar">
      <!-- 左：品牌 -->
      <div class="topbar-brand">
        <img src="/favicon.svg" alt="Knoa" class="topbar-logo" />
        <span class="topbar-title">企业智能知识库系统</span>
      </div>

      <!-- 中：导航链接 -->
      <nav class="topbar-nav">
        <router-link
          v-for="item in topNavItems"
          :key="item.to"
          :to="item.to"
          class="topbar-link"
          :class="{ active: route.path.startsWith(item.to) }"
        >{{ item.label }}</router-link>
      </nav>

      <!-- 右：操作区 -->
      <div class="topbar-right">
        <!-- 通知铃铛 + badge -->
        <button class="icon-btn notify-btn" title="通知">
          <Icon name="bell" :size="18" />
          <span class="notify-badge">1</span>
        </button>

        <!-- 全局搜索 -->
        <div class="topbar-search">
          <Icon name="search" :size="14" class="topbar-search-icon" />
          <input type="text" placeholder="全局搜索..." class="topbar-search-input" />
        </div>

        <!-- 用户头像 + 下拉 -->
        <div class="user-trigger" @click.stop="toggleUserMenu">
          <span class="avatar">{{ userInitial }}</span>
          <span class="user-name">{{ user?.name || '管理员' }}</span>
          <Icon name="chevron-down" :size="12" class="user-chev" />

          <div v-if="userMenuOpen" class="user-dropdown" @click.stop>
            <a class="dd-item" href="#" @click.prevent="router.push('/profile')">
              <Icon name="user" :size="16" />个人中心
            </a>
            <a class="dd-item" href="#" @click.prevent="router.push('/permission')">
              <Icon name="settings" :size="16" />账号设置
            </a>
            <div class="dd-divider" />
            <a class="dd-item dd-danger" href="#" @click.prevent="onLogout">
              <Icon name="logout" :size="16" />退出登录
            </a>
          </div>
        </div>
      </div>
    </header>

    <!-- ====== 主体：左侧边栏 + 内容区 ====== -->
    <div class="body-row">
      <!-- 左侧子菜单 -->
      <aside v-if="currentSubItems.length" class="sub-sidebar">
        <div class="sub-sidebar-header">{{ (route.meta.title as string) || '' }}</div>
        <div class="sub-nav">
          <button
            v-for="(item, i) in currentSubItems"
            :key="item.label"
            class="sub-item"
            :class="{ active: activeSub === i }"
            @click="activeSub = i"
          >
            <Icon v-if="item.icon" :name="item.icon" :size="16" />
            <span>{{ item.label }}</span>
          </button>
        </div>
        <div class="sub-footer">
          <button class="sub-collapse">
            <Icon name="collapse" :size="14" /> 收起菜单
          </button>
        </div>
      </aside>

      <!-- 主内容区 -->
      <main class="main-content">
        <router-view v-slot="{ Component }">
          <component :is="Component" :active-tab="activeSub" />
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--bg-page);
  border: none;
  outline: none;
}

/* ==================== 顶部导航栏 ==================== */
.topbar {
  height: var(--topbar-h);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 0 24px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 100;
  gap: 32px;
}

.topbar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.topbar-logo {
  width: 28px;
  height: 28px;
  border-radius: 7px;
}
.topbar-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
  white-space: nowrap;
}

/* 顶部导航链接 */
.topbar-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}
.topbar-link {
  padding: 7px 16px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  text-decoration: none;
  transition: all var(--dur-fast) var(--ease-out);
  white-space: nowrap;
}
.topbar-link:hover {
  color: var(--brand);
  background: var(--brand-soft);
}
.topbar-link.active {
  color: var(--brand);
  font-weight: 600;
  background: var(--brand-soft);
}

/* 右侧操作 */
.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

/* 通知铃铛 */
.notify-btn {
  position: relative;
}
.notify-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--danger);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  border: 2px solid var(--bg-surface);
}

/* 顶部全局搜索 */
.topbar-search {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  width: 200px;
  transition: border-color var(--dur-fast), box-shadow var(--dur-fast);
}
.topbar-search:focus-within {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.topbar-search-icon {
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.topbar-search-input {
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--text-primary);
  width: 100%;
}
.topbar-search-input::placeholder {
  color: var(--text-placeholder);
}

/* 用户触发器 */
.user-trigger {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px 4px 4px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--dur-fast);
}
.user-trigger:hover {
  background: var(--bg-hover);
}
.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--brand);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.user-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}
.user-chev {
  color: var(--text-tertiary);
}

/* 用户下拉菜单 */
.user-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 180px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-pop);
  padding: 6px;
  z-index: 200;
  animation: fade-up 0.15s ease both;
}
.dd-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--dur-fast), color var(--dur-fast);
  text-decoration: none;
}
.dd-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.dd-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 6px;
}
.dd-danger:hover {
  background: var(--danger-soft);
  color: var(--danger);
}

/* ==================== 主体行：子侧栏 + 内容 ==================== */
.body-row {
  display: flex;
  flex: 1;
  min-height: 0;
}

/* 左侧子侧栏 */
.sub-sidebar {
  width: var(--sidebar-w);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg-surface);
  padding-top: 20px;
  overflow-y: auto;
}
.sub-sidebar-header {
  padding: 0 18px 14px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}
.sub-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}
.sub-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 18px;
  border: none;
  background: transparent;
  border-radius: 0;
  font-size: 13px;
  font-family: inherit;
  color: var(--text-secondary);
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition: all var(--dur-fast) var(--ease-out);
}
.sub-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.sub-item.active {
  color: var(--brand);
  font-weight: 600;
  background: var(--brand-soft);
  border-right: 3px solid var(--brand);
}

.sub-footer {
  padding: 12px 18px;
  margin-top: auto;
}
.sub-collapse {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid var(--border);
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-tertiary);
  cursor: pointer;
  font-family: inherit;
  transition: all var(--dur-fast) var(--ease-out);
  width: 100%;
  justify-content: center;
}
.sub-collapse:hover {
  background: var(--bg-hover);
  color: var(--text-secondary);
  border-color: var(--border-strong);
}

/* 主内容区 */
.main-content {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 24px 28px;
}
</style>
