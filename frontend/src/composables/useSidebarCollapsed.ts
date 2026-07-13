import { ref } from 'vue'

/** 模块级单例：侧栏折叠状态，路由切换不丢失 */
const collapsed = ref(false)

export function useSidebarCollapsed() {
  return { collapsed }
}
