// 统一的鉴权头：从 localStorage 读取 token，注入到所有 API 请求。
const TOKEN_KEY = 'knoa_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// 全局 fetch 包装：捕获后端下发的滑动令牌（X-Access-Token 响应头），
// 自动写回 localStorage。后端每次有效认证请求都会重签 24h 令牌，
// 因此只要用户持续操作，token 就不会过期（闲置 >24h 才失效）。
const _nativeFetch = window.fetch.bind(window)
async function fetchWithSliding(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const resp = await _nativeFetch(input, init)
  const sliding = resp.headers.get('X-Access-Token')
  if (sliding) setToken(sliding)
  return resp
}
window.fetch = fetchWithSliding as typeof window.fetch
