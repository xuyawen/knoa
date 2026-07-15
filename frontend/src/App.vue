<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'

const auth = useAuthStore()
const chat = useChatStore()
const route = useRoute()
const router = useRouter()

function onKeydown(e: KeyboardEvent) {
  // ⌘K (Mac) / Ctrl+K (Win) 全局唤起提问
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    if (route.path !== '/') {
      router.push('/').then(() => chat.focusComposer())
    } else {
      chat.focusComposer()
    }
  }
}

onMounted(() => {
  if (auth.isAuthed) auth.fetchMe()
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="app-root">
    <router-view />
  </div>
</template>

<style scoped>
.app-root {
  height: 100%;
  overflow: hidden;
}
</style>
