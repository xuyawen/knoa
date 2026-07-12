import { createRouter, createWebHistory } from 'vue-router'
import Workbench from '@/views/Workbench.vue'
import KnowledgeBases from '@/views/KnowledgeBases.vue'
import KnowledgeBaseDetail from '@/views/KnowledgeBaseDetail.vue'
import ChatHistory from '@/views/ChatHistory.vue'
import Login from '@/views/Login.vue'
import Users from '@/views/Users.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: Login },
    { path: '/', name: 'workbench', component: Workbench },
    { path: '/knowledge-bases', name: 'knowledge-bases', component: KnowledgeBases },
    { path: '/knowledge-bases/:id', name: 'knowledge-base-detail', component: KnowledgeBaseDetail },
    { path: '/history', name: 'chat-history', component: ChatHistory },
    { path: '/users', name: 'users', component: Users, meta: { requiresAdmin: true } },
  ],
})

// 全局守卫：未登录跳登录；已登录访问登录页回首页；admin 页仅 admin
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.isAuthed) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && auth.isAuthed) {
    return { path: '/' }
  }
  if (to.meta?.requiresAdmin && !auth.isAdmin) {
    return { path: '/' }
  }
})

export default router
