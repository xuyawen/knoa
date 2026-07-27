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
import { request, requestVoid } from './http'

export async function login(username: string, password: string): Promise<TokenOut> {
  return request('/api/auth/login', { method: 'POST', json: { username, password } })
}

export async function getMe(): Promise<UserOut> {
  return request('/api/auth/me')
}

/** 退出登录：后端清除 HttpOnly Cookie（前端 fetch 带 credentials:'include'）。
 *  失败也无所谓（本地状态照常清理），所以不走 request 封装、不抛错。 */
export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST' }).catch(() => undefined)
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
  return request(`/api/auth/users?${params.toString()}`)
}

/** 新建用户（仅 admin）。 */
export async function createUser(payload: UserCreate): Promise<UserOut> {
  return request('/api/auth/users', { method: 'POST', json: payload })
}

/** 更新用户（改角色 / 停用启用 / 重置密码，仅 admin）。 */
export async function updateUser(id: string, payload: UserUpdate): Promise<UserOut> {
  return request(`/api/auth/users/${id}`, { method: 'PATCH', json: payload })
}

/** 删除用户（仅 admin；后端禁止删自己 / 删最后一个 admin）。 */
export async function deleteUser(id: string): Promise<void> {
  await requestVoid(`/api/auth/users/${id}`, { method: 'DELETE' })
}

/** 修改密码（验证旧密码 + 设新密码）。 */
export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  await requestVoid('/api/auth/change-password', {
    method: 'PUT',
    json: { oldPassword, newPassword },
  })
}

/* ── 角色管理（仅用户管理员） ── */

/** 角色列表（含权限集合）。 */
export async function getRoles(): Promise<RoleOut[]> {
  return request('/api/roles')
}

/** 新建自定义角色。 */
export async function createRole(payload: RoleCreate): Promise<RoleOut> {
  return request('/api/roles', { method: 'POST', json: payload })
}

/** 编辑角色名称/描述。 */
export async function updateRole(id: string, payload: RoleUpdate): Promise<RoleOut> {
  return request(`/api/roles/${id}`, { method: 'PUT', json: payload })
}

/** 设置某角色的权限集合（全量覆盖）。 */
export async function setRolePermissions(id: string, payload: RolePermissions): Promise<RoleOut> {
  return request(`/api/roles/${id}/permissions`, { method: 'PUT', json: payload })
}

/** 删除自定义角色。 */
export async function deleteRole(id: string): Promise<void> {
  await requestVoid(`/api/roles/${id}`, { method: 'DELETE' })
}
