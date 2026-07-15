<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { onTokenExpired } from '@/api/http'
import CommandPalette from '@/components/CommandPalette.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import Toast from '@/components/Toast.vue'
import AuthExpiredModal from '@/components/AuthExpiredModal.vue'

const auth = useAuthStore()
const router = useRouter()

const authExpiredOpen = ref(false)

// 任意接口返回 401（token 失效）→ 弹出不可关闭的重登录框
onTokenExpired(() => {
  authExpiredOpen.value = true
})

function onAuthExpiredConfirm() {
  auth.logout()
  router.replace('/login')
}

onMounted(() => {
  if (auth.isAuthed) auth.fetchMe()
})
</script>

<template>
  <div class="app-root">
    <router-view />
    <CommandPalette />
    <ConfirmDialog />
    <Toast />
    <AuthExpiredModal :open="authExpiredOpen" @confirm="onAuthExpiredConfirm" />
  </div>
</template>

<style scoped>
.app-root {
  height: 100%;
  overflow: hidden;
}
</style>
