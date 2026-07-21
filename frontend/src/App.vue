<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useThemeStore } from './stores/theme'
import { useAuthStore } from './stores/auth'
import { onTokenExpired, resetTokenExpired } from './api/http'
import { useRouter } from 'vue-router'
import Toast from './components/ui/Toast.vue'
import AuthExpiredModal from './components/ui/AuthExpiredModal.vue'

const theme = useThemeStore()
const auth = useAuthStore()
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
</script>

<template>
  <router-view />
  <Toast />
  <AuthExpiredModal :show="authExpiredOpen" @relogin="onAuthExpiredConfirm" />
</template>
