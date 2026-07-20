<script setup lang="ts">
import { onMounted } from 'vue'
import { useThemeStore } from './stores/theme'
import Toast from './components/ui/Toast.vue'

const theme = useThemeStore()

onMounted(() => {
  theme.init()
})
</script>

<template>
  <router-view />
  <Toast />
</template>
