import type { TokenOut, UserCreate, UserOut } from '@/types/api'
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
