import { reactive } from 'vue'

export type ToastType = 'success' | 'error'

const state = reactive({
  visible: false,
  message: '',
  type: 'success' as ToastType,
})

let timer: ReturnType<typeof setTimeout> | undefined

function show(message: string, type: ToastType, duration = 3000) {
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
