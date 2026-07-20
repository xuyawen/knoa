import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

// 路由表：认证页（Login）在布局外；其余业务页挂在 AppLayout 下。
// 注意：当前为"界面壳"阶段，auth 守卫用 mock 登录态，默认已登录以便浏览全部页面。
// 功能接入阶段再把守卫换成真实 token 校验。
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

export default router
