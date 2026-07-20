import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

// 认证 store（界面壳阶段为 mock，不接后端）。
// 默认已登录，便于浏览全部业务页面；功能接入阶段替换为真实登录态 + token。
export interface MockUser {
  id: string
  name: string
  role: 'admin' | 'editor' | 'viewer'
  dept: string
  avatarColor: string
}

const MOCK_USER: MockUser = {
  id: 'u_admin',
  name: '管理员',
  role: 'admin',
  dept: '技术中心',
  avatarColor: '#014DB2',
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<MockUser | null>(MOCK_USER)
  const isLoggedIn = computed(() => user.value !== null)

  // TODO(功能接入): 替换为真实登录请求 + token 持久化
  function login(_username: string, _password: string) {
    user.value = MOCK_USER
  }

  function logout() {
    user.value = null
  }

  return { user, isLoggedIn, login, logout }
})
