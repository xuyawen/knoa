import type { TokenOut, UserCreate, UserOut, UserUpdate } from '@/types/api'
import { authHeaders } from './http'

export async function login(username: string, password: string): Promise<TokenOut> {
  const resp = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

export async function getMe(): Promise<UserOut> {
  const resp = await fetch('/api/auth/me', { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 用户列表（仅 admin）。 */
export async function getUserList(): Promise<UserOut[]> {
  const resp = await fetch('/api/auth/users', { headers: authHeaders() })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

/** 新建用户（仅 admin）。 */
export async function createUser(payload: UserCreate): Promise<UserOut> {
  const resp = await fetch('/api/auth/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** 更新用户（改角色 / 停用启用 / 重置密码，仅 admin）。 */
export async function updateUser(id: string, payload: UserUpdate): Promise<UserOut> {
  const resp = await fetch(`/api/auth/users/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** 删除用户（仅 admin；后端禁止删自己 / 删最后一个 admin）。 */
export async function deleteUser(id: string): Promise<void> {
  const resp = await fetch(`/api/auth/users/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!resp.ok && resp.status !== 204) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
}

/** 修改密码（验证旧密码 + 设新密码）。 */
export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  const resp = await fetch('/api/auth/change-password', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ oldPassword, newPassword }),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
}
