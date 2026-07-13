<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

onMounted(() => {
  if (auth.isAuthed) auth.fetchMe()
})
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
