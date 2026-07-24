// 鉴权统一走 HttpOnly Cookie（由浏览器自动随请求携带，JS 读不到，防 XSS 窃取）。
// 因此这里不再注入 Authorization 头；跨域时 fetch 需 credentials:'include'（见 trackedFetch）。
import { report } from '../lib/monitor'

export function authHeaders(): Record<string, string> {
  return {}
}

// 统一的 HTTP 错误转换：把后端非 2xx 响应转成「用户友好」的 Error。
// 关键：5xx 不把后端原始内部错误回显给用户（可能含栈/路径），统一兜底文案；
// 4xx 优先沿用后端返回的业务文案（detail），"HTTP xxx" 这类无意义文案用映射覆盖。
const HTTP_MSG: Record<number, string> = {
  400: '请求参数有误',
  401: '登录状态已失效，请重新登录',
  403: '无权限执行此操作',
  404: '请求的资源不存在',
  413: '上传内容过大',
  422: '输入信息格式有误，请检查',
  429: '操作过于频繁，请稍后再试',
  500: '服务器繁忙，请稍后再试',
  502: '服务暂时不可用，请稍后再试',
  503: '服务正在维护中，请稍后再试',
}

export async function throwHttpError(resp: Response, fallback?: string): Promise<never> {
  const defaultMsg = HTTP_MSG[resp.status] || fallback || `请求失败(${resp.status})`
  let detail = ''
  try {
    const body = (await resp.json().catch(() => null)) as { detail?: unknown } | null
    if (typeof body?.detail === 'string') detail = body.detail
  } catch {
    /* 非 JSON 响应，忽略 */
  }
  // 后端若回显了 "HTTP xxx" 这类无意义文案，用友好映射覆盖
  if (/^HTTP \d+$/.test(detail)) detail = ''
  throw new Error(detail || defaultMsg)
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
