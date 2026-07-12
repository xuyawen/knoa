<script setup lang="ts">
// 应用根：仅承载路由视图，布局由 Workbench 负责（侧栏+顶栏+主体）。
// 历史会话抽屉为全局浮层，挂在这里以便任意页面都能打开。
import HistoryDrawer from '@/components/HistoryDrawer.vue'
</script>

<template>
  <div class="app-root">
    <router-view />
    <HistoryDrawer />
  </div>
</template>

<style scoped>
.app-root {
  height: 100%;
  overflow: hidden;
}
</style>
