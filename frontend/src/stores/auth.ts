import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getMe, login as apiLogin } from '@/api/auth'
import { getToken, setToken } from '@/api/http'
import type { UserOut } from '@/types/api'

const USER_KEY = 'knoa_user'

export interface CurrentUser {
  id: string
  username: string
  displayName: string | null
  role: string // admin | editor | viewer
  isActive: boolean
  createdAt: string | null
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const user = ref<CurrentUser | null>(
    (() => {
      const raw = localStorage.getItem(USER_KEY)
      return raw ? (JSON.parse(raw) as CurrentUser) : null
    })(),
  )

  const isAuthed = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isEditor = computed(() => user.value?.role === 'admin' || user.value?.role === 'editor')

  function persist() {
    setToken(token.value)
    if (user.value) localStorage.setItem(USER_KEY, JSON.stringify(user.value))
    else localStorage.removeItem(USER_KEY)
  }

  function _map(u: UserOut): CurrentUser {
    return {
      id: u.id,
      username: u.username,
      displayName: u.displayName,
      role: u.role,
      isActive: u.isActive,
      createdAt: u.createdAt,
    }
  }

  async function login(username: string, password: string) {
    const res = await apiLogin(username, password)
    token.value = res.accessToken
    user.value = _map(res.user)
    persist()
  }

  async function fetchMe() {
    if (!token.value) return
    try {
      user.value = _map(await getMe())
      persist()
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = null
    user.value = null
    persist()
  }

  return { token, user, isAuthed, isAdmin, isEditor, login, fetchMe, logout }
})
