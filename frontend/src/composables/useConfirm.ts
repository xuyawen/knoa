import { reactive } from 'vue'

export interface ConfirmOptions {
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  /** 危险模式：确认按钮变红 + 警告三角图标 */
  danger?: boolean
  /** 自定义图标名（覆盖 danger 默认图标） */
  icon?: string
  /** 点击确认后执行的异步回调；失败则留在弹窗、不关闭 */
  onConfirm?: () => Promise<void> | void
}

interface ConfirmState {
  visible: boolean
  title: string
  message: string
  confirmText: string
  cancelText: string
  danger: boolean
  icon: string
  loading: boolean
}

const state = reactive<ConfirmState>({
  visible: false,
  title: '确认操作',
  message: '',
  confirmText: '确认',
  cancelText: '取消',
  danger: false,
  icon: 'alert-triangle',
  loading: false,
})

let resolveFn: (v: boolean) => void = () => {}
let pendingConfirm: (() => Promise<void> | void) | undefined

/** 全局单例状态，供 ConfirmDialog 组件渲染 */
export function useConfirmState() {
  return state
}

/**
 * 打开一个漂亮的二次确认弹窗。
 * 直接 `await confirm({ message: '...' })`，返回 true 表示用户点了确认。
 * 可传 onConfirm 异步回调：执行期间确认按钮转圈禁用，成功才关闭。
 */
export function useConfirm() {
  function confirm(opts: ConfirmOptions): Promise<boolean> {
    pendingConfirm = opts.onConfirm
    state.title = opts.title ?? '确认操作'
    state.message = opts.message
    state.confirmText = opts.confirmText ?? '确认'
    state.cancelText = opts.cancelText ?? '取消'
    state.danger = opts.danger ?? false
    state.icon = opts.icon ?? (opts.danger ? 'alert-triangle' : 'help-circle')
    state.loading = false
    state.visible = true
    return new Promise<boolean>((resolve) => {
      resolveFn = resolve
    })
  }

  async function onConfirmClick() {
    if (state.loading) return
    if (pendingConfirm) {
      state.loading = true
      try {
        await pendingConfirm()
      } catch (e) {
        state.loading = false
        return
      }
    }
    state.visible = false
    resolveFn(true)
  }

  function onCancelClick() {
    if (state.loading) return
    state.visible = false
    resolveFn(false)
  }

  return { confirm, onConfirmClick, onCancelClick }
}
