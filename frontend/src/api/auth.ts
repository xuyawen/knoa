import type {
  Paginated,
  RoleCreate,
  RoleOut,
  RolePermissions,
  RoleUpdate,
  TokenOut,
  UserCreate,
  UserOut,
  UserUpdate,
} from '@/types/api'
import { authHeaders, throwHttpError } from './http'

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

/* ── 角色管理（仅用户管理员） ── */

/** 角色列表（含权限集合）。 */
export async function getRoles(): Promise<RoleOut[]> {
  const resp = await fetch('/api/roles', { headers: authHeaders() })
  if (!resp.ok) await throwHttpError(resp)
  return resp.json()
}

/** 新建自定义角色。 */
export async function createRole(payload: RoleCreate): Promise<RoleOut> {
  const resp = await fetch('/api/roles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) await throwHttpError(resp)
  return resp.json()
}

/** 编辑角色名称/描述。 */
export async function updateRole(id: string, payload: RoleUpdate): Promise<RoleOut> {
  const resp = await fetch(`/api/roles/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) await throwHttpError(resp)
  return resp.json()
}

/** 设置某角色的权限集合（全量覆盖）。 */
export async function setRolePermissions(id: string, payload: RolePermissions): Promise<RoleOut> {
  const resp = await fetch(`/api/roles/${id}/permissions`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) await throwHttpError(resp)
  return resp.json()
}

/** 删除自定义角色。 */
export async function deleteRole(id: string): Promise<void> {
  const resp = await fetch(`/api/roles/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!resp.ok && resp.status !== 204) await throwHttpError(resp)
}
