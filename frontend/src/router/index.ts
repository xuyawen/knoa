import { createRouter, createWebHistory } from 'vue-router'
import Workbench from '@/views/Workbench.vue'
import KnowledgeBases from '@/views/KnowledgeBases.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'workbench', component: Workbench },
    { path: '/knowledge-bases', name: 'knowledge-bases', component: KnowledgeBases },
  ],
})

export default router
