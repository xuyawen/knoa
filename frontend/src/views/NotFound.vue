<script setup lang="ts">
import { useRouter } from 'vue-router'
import Icon from '@/components/ui/Icon.vue'
const router = useRouter()
</script>

<template>
  <div class="nf">
    <div class="nf-code">404</div>
    <h1>页面走丢了</h1>
    <p>你访问的页面不存在或已被移动。</p>
    <button class="btn btn-primary" @click="router.push('/dashboard')">
      <Icon name="dashboard" :size="15" />返回首页
    </button>
  </div>
</template>

<style scoped>
.nf {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
  background: var(--bg-page);
}
.nf-code {
  font-size: 72px;
  font-weight: 800;
  color: var(--brand);
  letter-spacing: -0.03em;
  line-height: 1;
}
.nf h1 { margin: 0; font-size: 22px; }
.nf p { margin: 0 0 8px; color: var(--text-secondary); }
</style>
