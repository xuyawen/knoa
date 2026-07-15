<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import CommandPalette from '@/components/CommandPalette.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import Toast from '@/components/Toast.vue'

const auth = useAuthStore()

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
  </div>
</template>

<style scoped>
.app-root {
  height: 100%;
  overflow: hidden;
}
</style>
