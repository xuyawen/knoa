<script setup lang="ts">
// 应用根：仅承载路由视图，布局由 Workbench 负责（侧栏+顶栏+主体）。
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
