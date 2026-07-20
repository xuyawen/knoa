import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 路由表：认证页（Login）在布局外；其余业务页挂在 AppLayout 下。
// auth 守卫以 HttpOnly Cookie 为准：进入受保护页前，若无登录态则尝试用已有
// Cookie 还原（仅一次）；还原失败跳登录页（带 redirect 回跳参数）。
import Login from '@/views/Login.vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import Dashboard from '@/views/Dashboard.vue'
import Documents from '@/views/Documents.vue'
import Search from '@/views/Search.vue'
import Chat from '@/views/Chat.vue'
import Graph from '@/views/Graph.vue'
import Permission from '@/views/Permission.vue'
import NotFound from '@/views/NotFound.vue'

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: Login, meta: { public: true } },
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'dashboard', component: Dashboard, meta: { title: '首页大盘', icon: 'dashboard' } },
      { path: 'documents', name: 'documents', component: Documents, meta: { title: '文档管理', icon: 'doc' } },
      { path: 'search', name: 'search', component: Search, meta: { title: '智能搜索', icon: 'search' } },
      { path: 'chat', name: 'chat', component: Chat, meta: { title: 'AI 智能问答', icon: 'chat' } },
      { path: 'graph', name: 'graph', component: Graph, meta: { title: '知识图谱', icon: 'graph' } },
      { path: 'permission', name: 'permission', component: Permission, meta: { title: '权限管理', icon: 'shield' } },
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
