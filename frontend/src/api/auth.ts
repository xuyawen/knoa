import type { Paginated, TokenOut, UserCreate, UserOut, UserUpdate } from '@/types/api'
import { authHeaders } from './http'

const HTTP_MSG: Record<number, string> = {
  400: '请求参数有误',
  401: '用户名或密码错误',
  403: '无权限执行此操作',
  404: '请求的资源不存在',
  413: '上传内容过大',
  422: '输入信息格式有误，请检查',
  429: '操作过于频繁，请稍后再试',
  500: '服务器繁忙，请稍后再试',
  502: '服务暂时不可用，请稍后再试',
  503: '服务正在维护中，请稍后再试',
}

/** 从响应中提取用户友好的错误信息并抛出。 */
async function throwHttpError(resp: Response, fallback?: string): Promise<never> {
  const defaultMsg = HTTP_MSG[resp.status] || fallback || `请求失败(${resp.status})`
  let detail = ''
  try {
    const body = await resp.json()
    detail = body?.detail ?? ''
  } catch {
    /* 非 JSON 响应，忽略 */
  }
  // 后端返回的仍是 "HTTP xxx" 格式 → 用友好映射覆盖
  if (/^HTTP \d+$/.test(detail)) detail = ''
  throw new Error(detail || defaultMsg)
}

export async function login(username: string, password: string): Promise<TokenOut> {
  const resp = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!resp.ok) await throwHttpError(resp)
  return resp.json()
}

export async function getMe(): Promise<UserOut> {
  const resp = await fetch('/api/auth/me', { headers: authHeaders() })
  if (!resp.ok) await throwHttpError(resp)
  return resp.json()
}

/** 退出登录：后端清除 HttpOnly Cookie（前端 fetch 带 credentials:'include'）。 */
export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST', headers: authHeaders() })
}

/** 用户列表（仅 admin，分页 + 角色/关键词过滤）。 */
export async function getUserList(
  page = 1,
  size = 20,
  role?: string | null,
  q?: string | null,
): Promise<Paginated<UserOut>> {
  const params = new URLSearchParams()
  params.set('page', String(page))
  params.set('size', String(size))
  if (role) params.set('role', role)
  if (q) params.set('q', q)
  const resp = await fetch(`/api/auth/users?${params.toString()}`, { headers: authHeaders() })
  if (!resp.ok) await throwHttpError(resp)
  return resp.json()
}

/** 新建用户（仅 admin）。 */
export async function createUser(payload: UserCreate): Promise<UserOut> {
  const resp = await fetch('/api/auth/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) await throwHttpError(resp)
  return resp.json()
}

/** 更新用户（改角色 / 停用启用 / 重置密码，仅 admin）。 */
export async function updateUser(id: string, payload: UserUpdate): Promise<UserOut> {
  const resp = await fetch(`/api/auth/users/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) await throwHttpError(resp)
  return resp.json()
}

/** 删除用户（仅 admin；后端禁止删自己 / 删最后一个 admin）。 */
export async function deleteUser(id: string): Promise<void> {
  const resp = await fetch(`/api/auth/users/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!resp.ok && resp.status !== 204) await throwHttpError(resp)
}

/** 修改密码（验证旧密码 + 设新密码）。 */
export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  const resp = await fetch('/api/auth/change-password', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ oldPassword, newPassword }),
  })
  if (!resp.ok) await throwHttpError(resp)
}
