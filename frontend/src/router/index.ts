import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 路由表：认证页（Login）在布局外；其余业务页挂在 AppLayout 下。
// auth 守卫以 HttpOnly Cookie 为准：进入受保护页前，若无登录态则尝试用已有
// Cookie 还原（仅一次）；还原失败跳登录页（带 redirect 回跳参数）。
// 每个左侧子菜单项都是一条真实嵌套路由，由视图的 `section` prop 决定渲染内容，
// 因此每个菜单项都对应一个可收藏、URL 独立的完整页面。
import Login from '@/views/Login.vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import Dashboard from '@/views/Dashboard.vue'
import Documents from '@/views/Documents.vue'
import Search from '@/views/Search.vue'
import Chat from '@/views/Chat.vue'
import Graph from '@/views/Graph.vue'
import Permission from '@/views/Permission.vue'
import Profile from '@/views/Profile.vue'
import Settings from '@/views/Settings.vue'
import NotFound from '@/views/NotFound.vue'

// 子菜单分区 -> 路由段 + 默认 section
const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: Login, meta: { public: true } },
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      // ===== 首页大盘 =====
      { path: 'dashboard', name: 'dashboard', component: Dashboard, props: { section: 'overview' }, meta: { title: '首页大盘', icon: 'dashboard' } },
      { path: 'dashboard/analytics', name: 'dash-analytics', component: Dashboard, props: { section: 'analytics' }, meta: { title: '首页大盘', icon: 'chart' } },
      { path: 'dashboard/docs', name: 'dash-docs', component: Dashboard, props: { section: 'docs' }, meta: { title: '首页大盘', icon: 'doc' } },
      { path: 'dashboard/users', name: 'dash-users', component: Dashboard, props: { section: 'users' }, meta: { title: '首页大盘', icon: 'users' } },
      { path: 'dashboard/popular', name: 'dash-popular', component: Dashboard, props: { section: 'popular' }, meta: { title: '首页大盘', icon: 'fire' } },
      { path: 'dashboard/announcements', name: 'dash-announcements', component: Dashboard, props: { section: 'announcements' }, meta: { title: '首页大盘', icon: 'bell' } },

      // ===== 文档管理 =====
      { path: 'documents', name: 'documents', component: Documents, props: { section: 'mine' }, meta: { title: '文档管理', icon: 'doc' } },
      { path: 'documents/public', name: 'docs-public', component: Documents, props: { section: 'public' }, meta: { title: '文档管理', icon: 'globe' } },
      { path: 'documents/department', name: 'docs-department', component: Documents, props: { section: 'department' }, meta: { title: '文档管理', icon: 'team' } },
      { path: 'documents/archive', name: 'docs-archive', component: Documents, props: { section: 'archive' }, meta: { title: '文档管理', icon: 'archive' } },

      // ===== 智能搜索 =====
      { path: 'search', name: 'search', component: Search, props: { section: 'history' }, meta: { title: '智能搜索', icon: 'search' } },
      { path: 'search/popular', name: 'search-popular', component: Search, props: { section: 'popular' }, meta: { title: '智能搜索', icon: 'fire' } },
      { path: 'search/filters', name: 'search-filters', component: Search, props: { section: 'filters' }, meta: { title: '智能搜索', icon: 'filter' } },

      // ===== AI 智能问答 =====
      { path: 'chat', name: 'chat', component: Chat, props: { section: 'new' }, meta: { title: 'AI 智能问答', icon: 'chat' } },
      { path: 'chat/new', name: 'chat-new', component: Chat, props: { section: 'new' }, meta: { title: 'AI 智能问答', icon: 'plus' } },
      { path: 'chat/history', name: 'chat-history', component: Chat, props: { section: 'history' }, meta: { title: 'AI 智能问答', icon: 'history' } },
      { path: 'chat/records', name: 'chat-records', component: Chat, props: { section: 'records' }, meta: { title: 'AI 智能问答', icon: 'list' } },
      { path: 'chat/model', name: 'chat-model', component: Chat, props: { section: 'model' }, meta: { title: 'AI 智能问答', icon: 'settings' } },

      // ===== 知识图谱 =====
      { path: 'graph', name: 'graph', component: Graph, props: { section: 'global' }, meta: { title: '知识图谱', icon: 'graph' } },
      { path: 'graph/global', name: 'graph-global', component: Graph, props: { section: 'global' }, meta: { title: '知识图谱', icon: 'graph' } },
      { path: 'graph/nodes', name: 'graph-nodes', component: Graph, props: { section: 'nodes' }, meta: { title: '知识图谱', icon: 'node' } },
      { path: 'graph/relations', name: 'graph-relations', component: Graph, props: { section: 'relations' }, meta: { title: '知识图谱', icon: 'link' } },
      { path: 'graph/stats', name: 'graph-stats', component: Graph, props: { section: 'stats' }, meta: { title: '知识图谱', icon: 'chart' } },

      // ===== 其它一级页 =====
      { path: 'permission', name: 'permission', component: Permission, meta: { title: '权限管理', icon: 'shield' } },
      { path: 'profile', name: 'profile', component: Profile, meta: { title: '个人中心', icon: 'user' } },
      { path: 'settings', name: 'settings', component: Settings, meta: { title: '系统设置', icon: 'settings' } },
    ],
  },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFound },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// 登录态引导：仅一次用 HttpOnly Cookie 尝试还原；失败跳登录页。
let bootstrapped = false

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  // 公开页（登录）无需鉴权
  if (to.meta.public) return true

  if (!auth.isLoggedIn) {
    if (!bootstrapped) {
      await auth.fetchMe()
      bootstrapped = true
    }
    if (!auth.isLoggedIn) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
  return true
})

export default router
