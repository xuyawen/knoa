import { reactive } from 'vue'
import { isTokenExpired } from '@/api/http'

export type ToastType = 'success' | 'error'

const state = reactive({
  visible: false,
  message: '',
  type: 'success' as ToastType,
})

let timer: ReturnType<typeof setTimeout> | undefined

function show(message: string, type: ToastType, duration = 3000) {
  // token 已失效时，全局重登录弹窗接管 UI，抑制其它错误/成功提示
  if (isTokenExpired()) return
  state.message = message
  state.type = type
  state.visible = true
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    state.visible = false
  }, duration)
}

function dismiss() {
  state.visible = false
  if (timer) clearTimeout(timer)
}

export function useToast() {
  return {
    state,
    success: (message: string, duration?: number) => show(message, 'success', duration),
    error: (message: string, duration?: number) => show(message, 'error', duration),
    dismiss,
  }
}
