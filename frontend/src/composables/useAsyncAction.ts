import { ref } from 'vue'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'

// ── 统一异步动作守卫（防按钮连点重复提交） ──
// 网络层另有一道同请求在途去重兜底（api/http.ts withDedupe），
// 本守卫负责 UI 语义：busy 可绑定按钮 :disabled / ConfirmDialog :loading。
//
// 用法：
//   const { busy: saving, run } = useAsyncAction({ errorPrefix: '保存失败' })
//   async function submit() {
//     await run(async () => { await createX(...); toast.success('已创建') })
//   }
// 行级按钮（每行独立在途）用 useKeyedAsyncAction。

export interface AsyncActionOptions {
  /** 出错时自动 toast `${errorPrefix}：${errMsg(e)}`；与 onError 二选一 */
  errorPrefix?: string
  /** 自定义错误处理（优先于 errorPrefix）；两者都未指定时原样抛给调用方 */
  onError?: (e: unknown) => void
}

function handleError(e: unknown, o?: AsyncActionOptions): void {
  if (o?.onError) o.onError(e)
  else if (o?.errorPrefix) useToastStore().error(`${o.errorPrefix}：${errMsg(e)}`)
  else throw e
}

function mergeOpts(defaults?: AsyncActionOptions, opts?: AsyncActionOptions): AsyncActionOptions | undefined {
  if (!opts) return defaults
  return defaults ? { ...defaults, ...opts } : opts
}

/**
 * 单在途守卫：run 执行期间再次调用直接忽略（返回 undefined），
 * finally 恒复位 busy。defaults 为通用错误配置，单次 opts 可覆盖。
 */
export function useAsyncAction(defaults?: AsyncActionOptions) {
  const busy = ref(false)
  async function run<T>(fn: () => Promise<T>, opts?: AsyncActionOptions): Promise<T | undefined> {
    if (busy.value) return undefined
    busy.value = true
    try {
      return await fn()
    } catch (e: unknown) {
      handleError(e, mergeOpts(defaults, opts))
      return undefined
    } finally {
      busy.value = false
    }
  }
  return { busy, run }
}

/**
 * 按 key 的在途守卫：列表行级按钮（如逐行置顶/删除）各自独立 busy，
 * isBusy(key) 用于禁用对应行；不同 key 互不阻塞。
 */
export function useKeyedAsyncAction(defaults?: AsyncActionOptions) {
  const busyKeys = ref(new Set<string>())
  async function run<T>(key: string, fn: () => Promise<T>, opts?: AsyncActionOptions): Promise<T | undefined> {
    if (busyKeys.value.has(key)) return undefined
    busyKeys.value.add(key)
    try {
      return await fn()
    } catch (e: unknown) {
      handleError(e, mergeOpts(defaults, opts))
      return undefined
    } finally {
      busyKeys.value.delete(key)
    }
  }
  const isBusy = (key: string): boolean => busyKeys.value.has(key)
  return { busyKeys, run, isBusy }
}
