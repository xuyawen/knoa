// 统一的鉴权头：从 localStorage 读取 token，注入到所有 API 请求。
const TOKEN_KEY = 'knoa_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

// 前端可观测：非 401 的接口异常上报后端 /api/events（401 由 token 失效逻辑单独处理）
import { report } from '../lib/monitor'

// 鉴权统一走 HttpOnly Cookie（由浏览器自动随请求携带，JS 读不到，防 XSS 窃取）。
// 因此这里不再注入 Authorization 头；跨域时 fetch 需 credentials:'include'（见 trackedFetch）。
export function authHeaders(): Record<string, string> {
  return {}
}

// ── 统一 token 失效拦截 ──
// 后端对失效/无效的令牌统一返回 401（detail 如「令牌已过期」）。
// 任何 authed 接口一旦收到 401，就视为身份失效：取消所有在途请求，
// 并触发全局「请重新登录」弹窗（不可关闭，仅确定按钮 → 回登录页）。

export class TokenExpiredError extends Error {
  constructor() {
    super('身份凭证已失效')
    this.name = 'TokenExpiredError'
  }
}

const inFlight = new Set<AbortController>()
let tokenExpired = false
let expiredHandler: (() => void) | null = null

/** 当前是否已触发 token 失效（供 toast 等组件抑制后续提示）。 */
export function isTokenExpired(): boolean {
  return tokenExpired
}

/** 重置 token 失效状态（用户确认重登录弹窗后调用，允许重新登录）。 */
export function resetTokenExpired(): void {
  tokenExpired = false
}

/** 注册 token 失效回调（由 App 注册，用于弹出重登录框）。 */
export function onTokenExpired(fn: () => void): void {
  expiredHandler = fn
}

function triggerTokenExpired(): void {
  if (tokenExpired) return
  tokenExpired = true
  // 取消所有其它在途请求
  for (const c of inFlight) {
    try {
      c.abort()
    } catch {
      /* noop */
    }
  }
  inFlight.clear()
  expiredHandler?.()
}

/** 合并多个 AbortSignal（优先用 AbortSignal.any，低版本浏览器降级手动合并）。 */
function mergeSignals(signals: AbortSignal[]): AbortSignal {
  const anyFn = (AbortSignal as unknown as { any?: (s: AbortSignal[]) => AbortSignal }).any
  if (typeof anyFn === 'function') return anyFn(signals)
  const ctrl = new AbortController()
  for (const s of signals) {
    if (s.aborted) ctrl.abort()
    else s.addEventListener('abort', () => ctrl.abort(), { once: true })
  }
  return ctrl.signal
}

function reqUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.href
  return (input as Request).url ?? ''
}

const _nativeFetch = window.fetch.bind(window)

async function trackedFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  // 已经失效则快速失败，不再发起任何网络请求（登录接口例外）
  const url = reqUrl(input)
  if (tokenExpired && !url.includes('/api/auth/login')) throw new TokenExpiredError()

  const ctrl = new AbortController()
  const signals: AbortSignal[] = [ctrl.signal]
  if (init?.signal) signals.push(init.signal as AbortSignal)

  const mergedInit: RequestInit = {
    ...init,
    // 携带 HttpOnly Cookie（含跨域场景）
    credentials: 'include',
    signal: mergeSignals(signals),
  }

  inFlight.add(ctrl)
  try {
    const resp = await _nativeFetch(input, mergedInit)
    // 登录接口本身会返回 401（账号密码错误），那不是 token 失效，不拦截
    if (resp.status === 401 && !reqUrl(input).includes('/api/auth/login')) {
      triggerTokenExpired()
      throw new TokenExpiredError()
    }
    // 5xx 服务端错误：上报，便于 /api/metrics 看到前端视角的服务端异常
    if (resp.status >= 500) {
      report({ type: 'http.server_error', message: `${reqUrl(input)} -> ${resp.status}`, level: 'error' })
    }
    // 后端每次有效认证请求都会重签 24h 令牌（滑动令牌），并通过
    // Set-Cookie 回写 HttpOnly Cookie（前端 JS 读不到，无需在此处理）
    return resp
  } catch (err) {
    if (err instanceof TokenExpiredError) throw err
    // 网络层失败（断网/超时/CORS）fetch 会抛到这
    report({ type: 'http.network', message: `${reqUrl(input)} -> ${String(err)}`, level: 'error' })
    throw err
  } finally {
    inFlight.delete(ctrl)
  }
}

// 全局替换 fetch，使所有（含各 api 模块直接调用的）请求都经过统一拦截
window.fetch = trackedFetch as typeof window.fetch
