import { createRouter, createWebHistory } from 'vue-router'
import Workbench from '@/views/Workbench.vue'
import KnowledgeBases from '@/views/KnowledgeBases.vue'
import KnowledgeBaseDetail from '@/views/KnowledgeBaseDetail.vue'
import ChatHistory from '@/views/ChatHistory.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'workbench', component: Workbench },
    { path: '/knowledge-bases', name: 'knowledge-bases', component: KnowledgeBases },
    { path: '/knowledge-bases/:id', name: 'knowledge-base-detail', component: KnowledgeBaseDetail },
    { path: '/history', name: 'chat-history', component: ChatHistory },
  ],
})

export default router
