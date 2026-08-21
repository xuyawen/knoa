import { watch, onScopeDispose, type WatchSource } from 'vue'

// ── 全站搜索输入的统一节流 ──
// 约定：所有搜索表单「输入即搜索」（无需回车），但停止输入 delay 毫秒后才真正发请求，
// 避免逐键打爆后端。各处不再手写 setTimeout 防抖，统一走本 composable。
// flush:'sync' 使回调在赋值时同步入队，调用方赋值后立即 cancel() 可精确撤销待发的搜索。
export const SEARCH_DEBOUNCE_MS = 300

/**
 * 监听 source 变化，停顿 delay 毫秒后执行 cb；期间再次变化则重新计时。
 * 组件卸载（effect scope 销毁）自动清理定时器。
 * 返回 cancel：撤销待发的回调（如回车立即搜索时，避免随后重复触发一次）。
 */
export function useDebouncedWatch(source: WatchSource, cb: () => void, delay = SEARCH_DEBOUNCE_MS) {
  let timer: ReturnType<typeof setTimeout> | null = null
  watch(
    source,
    () => {
      if (timer) clearTimeout(timer)
      timer = setTimeout(() => {
        timer = null
        cb()
      }, delay)
    },
    { flush: 'sync' },
  )
  function cancel() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }
  onScopeDispose(cancel)
  return { cancel }
}
