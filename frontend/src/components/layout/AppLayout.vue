<script setup lang="ts">
// 布局壳：顶部水平导航栏（logo+主导航+用户）+ 左侧页面子菜单 + 右侧主内容。
// 按 6 张目标 UI 截图 1:1 还原。
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { getAnnouncements, markAnnouncementRead } from '@/api'
import type { Announcement } from '@/types/api'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import SystemSettingsPanel from '@/components/user/SystemSettingsPanel.vue'

const auth = useAuthStore()
const theme = useThemeStore()
const router = useRouter()
const route = useRoute()

/* ---------- 通知中心（P8）---------- */
const announcements = ref<Announcement[]>([])
const notifyOpen = ref(false)
const notifyLoading = ref(false)

const unreadCount = computed(() => announcements.value.filter((a) => !a.read).length)

async function loadAnnouncements() {
  notifyLoading.value = true
  try {
    announcements.value = (await getAnnouncements()).items
  } catch {
    announcements.value = []
  } finally {
    notifyLoading.value = false
  }
}

function toggleNotify() {
  notifyOpen.value = !notifyOpen.value
  if (notifyOpen.value && !announcements.value.length) loadAnnouncements()
}

async function markRead(a: Announcement) {
  if (a.read) return
  // 乐观更新，避免等待
  a.read = true
  try {
    await markAnnouncementRead(a.id)
  } catch {
    a.read = false
  }
}

function closeNotify() {
  notifyOpen.value = false
}

function goAnnouncements() {
  closeNotify()
  router.push('/dashboard/announcements')
}

onMounted(loadAnnouncements)

/* ---------- 顶部主导航 ---------- */
const topNavItems = [
  { to: '/dashboard', label: '首页大盘' },
  { to: '/chat', label: 'AI智能问答' },
  { to: '/documents', label: '文档管理' },
  { to: '/search', label: '智能搜索' },
  { to: '/graph', label: '知识图谱' },
  { to: '/permission', label: '系统管理' },
]

/* ---------- 左侧子菜单（每项都是真实路由）---------- */
interface SubItem {
  label: string
  icon?: string
  to: string                 // 点击跳转的路由
  activeNames: string[]      // 匹配哪些路由名时高亮（parent 与 detail 可能多个）
}

const subMenus: Record<string, SubItem[]> = {
  dashboard: [
    { label: '数据总览', icon: 'grid', to: '/dashboard', activeNames: ['dashboard'] },
    { label: '访问分析', icon: 'chart', to: '/dashboard/analytics', activeNames: ['dash-analytics'] },
    { label: '文档统计', icon: 'doc', to: '/dashboard/docs', activeNames: ['dash-docs'] },
    { label: '用户统计', icon: 'users', to: '/dashboard/users', activeNames: ['dash-users'] },
    { label: '热门内容', icon: 'fire', to: '/dashboard/popular', activeNames: ['dash-popular'] },
    { label: '系统公告', icon: 'bell', to: '/dashboard/announcements', activeNames: ['dash-announcements'] },
  ],
  documents: [
    { label: '我的文档', icon: 'folder', to: '/documents', activeNames: ['documents'] },
    { label: '公共文档', icon: 'globe', to: '/documents/public', activeNames: ['docs-public'] },
    { label: '部门文档', icon: 'team', to: '/documents/department', activeNames: ['docs-department'] },
    { label: '文档归档', icon: 'archive', to: '/documents/archive', activeNames: ['docs-archive'] },
  ],
  search: [
    { label: '搜索历史', icon: 'clock', to: '/search', activeNames: ['search'] },
    { label: '热门搜索', icon: 'fire', to: '/search/popular', activeNames: ['search-popular'] },
    { label: '搜索筛选', icon: 'filter', to: '/search/filters', activeNames: ['search-filters'] },
  ],
  chat: [
    { label: '新建对话', icon: 'plus', to: '/chat/new', activeNames: ['chat', 'chat-new'] },
    { label: '历史会话', icon: 'history', to: '/chat/history', activeNames: ['chat-history'] },
    { label: '问答记录', icon: 'list', to: '/chat/records', activeNames: ['chat-records'] },
    { label: '模型配置', icon: 'settings', to: '/chat/model', activeNames: ['chat-model'] },
  ],
  graph: [
    { label: '全局图谱', icon: 'graph', to: '/graph/global', activeNames: ['graph', 'graph-global'] },
    { label: '节点管理', icon: 'node', to: '/graph/nodes', activeNames: ['graph-nodes'] },
    { label: '关系检索', icon: 'link', to: '/graph/relations', activeNames: ['graph-relations'] },
    { label: '图谱统计', icon: 'chart', to: '/graph/stats', activeNames: ['graph-stats'] },
  ],
}

const currentSubItems = computed<SubItem[]>(() => {
  const p = route.path.replace(/^\//, '').split('/')[0]
  return subMenus[p] ?? []
})

function isSubActive(item: SubItem): boolean {
  return item.activeNames.includes(route.name as string)
}

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
function goAccountSettings() {
  closeUserMenu()
  showSettings.value = true
}

/* ---------- 账号设置弹框 ---------- */
const showSettings = ref(false)
const settingsSaving = ref(false)
const settingsRef = ref<InstanceType<typeof SystemSettingsPanel> | null>(null)

async function onSaveSettings() {
  if (!settingsRef.value) return
  settingsSaving.value = true
  try {
    await settingsRef.value.onSave()
  } finally {
    settingsSaving.value = false
  }
}

const user = computed(() => auth.user)
const userInitial = computed(() => user.value?.name?.[0] ?? '管')

/* ---------- 子侧栏折叠 ---------- */
const sidebarCollapsed = ref(false)
</script>

<template>
  <!-- 点击弹窗外部关闭通知/用户下拉；弹窗内部已 @click.stop -->
  <div class="layout" @click="closeUserMenu(); closeNotify()">
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
        <!-- 主题切换：明 / 暗 -->
        <button
          class="icon-btn theme-toggle"
          :title="theme.current === 'dark' ? '切换到明亮模式' : '切换到暗黑模式'"
          @click="theme.toggle()"
        >
          <Icon :name="theme.current === 'dark' ? 'sun' : 'moon'" :size="18" />
        </button>

        <!-- 通知铃铛 + badge -->
        <div class="notify-wrap">
          <button class="icon-btn notify-btn" title="通知" @click.stop="toggleNotify">
            <Icon name="bell" :size="18" />
            <span v-if="unreadCount" class="notify-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
          </button>

          <!-- 通知下拉 -->
          <div v-if="notifyOpen" class="notify-dropdown" @click.stop>
            <div class="notify-head">
              <span>通知</span>
              <button class="notify-link" @click="goAnnouncements">查看全部</button>
            </div>
            <div class="notify-body">
              <div v-if="notifyLoading" class="notify-loading">
                <Icon name="loader" :size="14" class="spin" /> 加载中…
              </div>
              <div v-else-if="!announcements.length" class="notify-empty">暂无通知</div>
              <button
                v-for="a in announcements"
                :key="a.id"
                class="notify-item"
                :class="{ unread: !a.read }"
                @click="markRead(a)"
              >
                <span class="ni-dot" :class="`lvl-${a.level}`" />
                <span class="ni-text">
                  <span class="ni-title">{{ a.title }}</span>
                  <span class="ni-content">{{ a.content }}</span>
                </span>
                <Icon v-if="!a.read" name="check" :size="14" class="ni-mark" />
              </button>
            </div>
          </div>
        </div>

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
            <a class="dd-item" href="#" @click.prevent="goAccountSettings">
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

    <!-- 账号设置弹框 -->
    <AppModal :show="showSettings" title="账号设置" wide @close="showSettings = false">
      <SystemSettingsPanel ref="settingsRef" />
      <template #foot>
        <button class="btn btn-ghost" @click="showSettings = false">关闭</button>
        <button class="btn btn-primary" :disabled="settingsSaving" @click="onSaveSettings">
          <Icon v-if="settingsSaving" name="loader" :size="14" class="spin" />
          {{ settingsSaving ? '保存中…' : '保存设置' }}
        </button>
      </template>
    </AppModal>

    <!-- ====== 主体：左侧边栏 + 内容区 ====== -->
    <div class="body-row">
      <!-- 左侧子菜单 -->
      <aside v-if="currentSubItems.length" class="sub-sidebar" :class="{ collapsed: sidebarCollapsed }">
        <div class="sub-sidebar-header">{{ (route.meta.title as string) || '' }}</div>
        <div class="sub-nav">
          <router-link
            v-for="item in currentSubItems"
            :key="item.label"
            :to="item.to"
            class="sub-item"
            :class="{ active: isSubActive(item) }"
          >
            <Icon v-if="item.icon" :name="item.icon" :size="16" />
            <span>{{ item.label }}</span>
          </router-link>
        </div>
        <div class="sub-footer">
          <button class="sub-collapse" @click="sidebarCollapsed = true">
            <Icon name="collapse" :size="14" /> 收起菜单
          </button>
        </div>
      </aside>

      <!-- 主内容区 -->
      <main class="main-content">
        <button
          v-if="sidebarCollapsed && currentSubItems.length"
          class="sidebar-expand"
          title="展开菜单"
          @click="sidebarCollapsed = false"
        >
          <Icon name="chevron-right" :size="16" />
        </button>
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
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
.notify-wrap { position: relative; }
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

/* 通知下拉 */
.notify-dropdown {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  width: 340px;
  max-height: 420px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-pop);
  z-index: 200;
  display: flex;
  flex-direction: column;
  animation: fade-up 0.15s ease both;
  overflow: hidden;
}
.notify-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border);
}
.notify-link {
  border: none;
  background: transparent;
  color: var(--brand);
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
}
.notify-body { overflow-y: auto; padding: 6px; }
.notify-loading, .notify-empty {
  padding: 28px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--text-tertiary);
}
.notify-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  padding: 11px 10px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  text-align: left;
  cursor: pointer;
  font-family: inherit;
  transition: background var(--dur-fast);
}
.notify-item:hover { background: var(--bg-hover); }
.notify-item.unread { background: var(--brand-soft); }
.ni-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
  background: var(--text-tertiary);
}
.ni-dot.lvl-info { background: var(--brand); }
.ni-dot.lvl-warning { background: #f59e0b; }
.ni-dot.lvl-error { background: var(--danger); }
.ni-dot.lvl-success { background: var(--success); }
.ni-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; flex: 1; }
.ni-title { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.ni-content {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ni-mark { color: var(--brand); flex-shrink: 0; margin-top: 3px; }

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
  transition: width var(--dur) var(--ease-out);
}
.sub-sidebar.collapsed {
  width: 0;
  min-width: 0;
  padding-top: 0;
  border-right: none;
  overflow: hidden;
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
  position: relative;
}
.sidebar-expand {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 20;
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.sidebar-expand:hover { background: var(--bg-hover); color: var(--text-primary); }
</style>
