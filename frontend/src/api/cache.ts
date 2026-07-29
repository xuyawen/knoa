/* ---------- 字典 / 列表接口缓存（P4）----------
 * 低频变化、被多处重复拉取的数据做 in-flight 去重 + 短 TTL 防重复调用。
 * - cachedDict(key, loader)：命中 5s 内缓存直接返回同一 Promise（含并发去重）；
 *   失败不缓存，下次调用重新请求。
 * - 读取接口支持 force=true 绕过缓存（刷新按钮用）。
 * - 写接口成功后按 key（或前缀）主动失效，避免列表看到旧数据。
 * 带参列表接口的 key 必须把参数拼进去，否则翻页会命中错误缓存。 */

const _dictCache = new Map<string, { at: number; p: Promise<unknown> }>()
export const DICT_TTL_MS = 5_000

export function cachedDict<T>(key: string, loader: () => Promise<T>): Promise<T> {
  const hit = _dictCache.get(key)
  if (hit && Date.now() - hit.at < DICT_TTL_MS) return hit.p as Promise<T>
  const p = loader().catch((e) => {
    // 失败不缓存，下次调用重新请求
    _dictCache.delete(key)
    throw e
  })
  _dictCache.set(key, { at: Date.now(), p })
  return p
}

/** 精确失效单个 key（无参接口用）。 */
export function invalidateDict(key: string) {
  _dictCache.delete(key)
}

/** 按前缀失效一组 key（带参列表接口用，如 'kb:' / 'doc:xxx:'）。 */
export function invalidateDictPrefix(prefix: string) {
  for (const k of _dictCache.keys()) {
    if (k.startsWith(prefix)) _dictCache.delete(k)
  }
}
