import { defineStore } from 'pinia'
import { ref } from 'vue'

// 轻量 Toast store：界面壳阶段即可用的提示组件（复用于后续功能）。
export interface ToastItem {
  id: number
  type: 'success' | 'error' | 'info' | 'warning'
  message: string
}

export const useToastStore = defineStore('toast', () => {
  const items = ref<ToastItem[]>([])
  let seq = 0

  function push(type: ToastItem['type'], message: string, duration = 2600) {
    const id = ++seq
    items.value.push({ id, type, message })
    window.setTimeout(() => dismiss(id), duration)
  }

  function dismiss(id: number) {
    items.value = items.value.filter((t) => t.id !== id)
  }

  return {
    items,
    dismiss,
    success: (m: string) => push('success', m),
    error: (m: string) => push('error', m),
    info: (m: string) => push('info', m),
    warning: (m: string) => push('warning', m),
  }
})
