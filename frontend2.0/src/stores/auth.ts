import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getMe, login as apiLogin, logout as apiLogout } from '@/api/auth'
import type { UserOut } from '@/types/api'

const USER_KEY = 'knoa_user'

// 壳兼容：AppLayout 顶栏消费 user.name（头像首字 + 显示名），
// 故在真实字段外补 name = displayName || username。
export interface CurrentUser {
  id: string
  username: string
  name: string
  displayName: string | null
  role: 'admin' | 'editor' | 'viewer'
  isActive: boolean
  createdAt: string | null
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(
    (() => {
      const raw = localStorage.getItem(USER_KEY)
      return raw ? (JSON.parse(raw) as CurrentUser) : null
    })(),
  )

  // 登录态由「后端能否凭 HttpOnly Cookie 解出当前用户」决定，
  // 不再依赖前端持有的明文 token（防 XSS 窃取）。
  const isLoggedIn = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isEditor = computed(
    () => user.value?.role === 'admin' || user.value?.role === 'editor',
  )

  function persist() {
    if (user.value) localStorage.setItem(USER_KEY, JSON.stringify(user.value))
    else localStorage.removeItem(USER_KEY)
  }

  function _map(u: UserOut): CurrentUser {
    return {
      id: u.id,
      username: u.username,
      name: u.displayName || u.username,
      displayName: u.displayName,
      role: (u.role as CurrentUser['role']) || 'viewer',
      isActive: u.isActive,
      createdAt: u.createdAt,
    }
  }

  async function login(username: string, password: string) {
    const res = await apiLogin(username, password)
    // 令牌已由后端写入 HttpOnly Cookie，前端不持有明文 token
    user.value = _map(res.user)
    persist()
  }

  async function fetchMe() {
    try {
      // 令牌在 HttpOnly Cookie 中，由后端校验；无有效 cookie 会 401 → 走退出逻辑
      user.value = _map(await getMe())
      persist()
    } catch {
      logout()
    }
  }

  async function logout() {
    // 清掉后端 HttpOnly Cookie（失效当前会话）
    await apiLogout().catch(() => {})
    user.value = null
    persist()
  }

  return { user, isLoggedIn, isAdmin, isEditor, login, fetchMe, logout }
})
