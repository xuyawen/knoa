import { createRouter, createWebHistory } from 'vue-router'
import Workbench from '@/views/Workbench.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', name: 'workbench', component: Workbench }],
})

export default router
