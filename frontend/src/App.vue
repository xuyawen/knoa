<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useThemeStore } from './stores/theme'
import { useAuthStore } from './stores/auth'
import { useKnowledgeStore } from './stores/knowledge'
import { onTokenExpired, resetTokenExpired } from './api/http'
import { useRouter } from 'vue-router'
import Toast from './components/ui/Toast.vue'
import AuthExpiredModal from './components/ui/AuthExpiredModal.vue'

const theme = useThemeStore()
const auth = useAuthStore()
const knowledge = useKnowledgeStore()
const router = useRouter()

const authExpiredOpen = ref(false)

// 任意接口返回 401（token 失效）→ 弹出不可关闭的重登录框
onTokenExpired(() => {
  authExpiredOpen.value = true
})

function onAuthExpiredConfirm() {
  authExpiredOpen.value = false
  auth.logout()
  resetTokenExpired() // 允许后续 login 请求正常发出
  router.replace('/login')
}

onMounted(() => {
  theme.init()
})

// 账号切换（登出 / 登入 / token 过期强制退出）→ 重置数据缓存，
// 避免新用户看到上一位用户的知识库列表（403 根因）。
watch(() => auth.user?.id, () => {
  knowledge.$reset()
})
</script>

<template>
  <router-view />
  <Toast />
  <AuthExpiredModal :show="authExpiredOpen" @relogin="onAuthExpiredConfirm" />
</template>
