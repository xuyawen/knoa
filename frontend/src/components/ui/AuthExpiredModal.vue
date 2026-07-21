<script setup lang="ts">
// 会话过期弹框：复用于登录态失效场景（token 过期/被踢）。
// 界面壳阶段仅为静态展示组件，功能接入后由拦截器触发。
import AppModal from './AppModal.vue'

withDefaults(defineProps<{ show: boolean }>(), { show: false })
const emit = defineEmits<{ (e: 'close'): void; (e: 'relogin'): void }>()
</script>

<template>
  <AppModal :show="show" :close-on-backdrop="false" @close="emit('close')">
    <div class="expired">
      <span class="expired-ic">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l9 16H3zM12 10v4M12 17v.5" /></svg>
      </span>
      <p class="expired-msg">登录状态已失效，请重新登录以继续使用。</p>
    </div>
    <template #foot>
      <button class="btn btn-primary" @click="emit('relogin')">重新登录</button>
    </template>
  </AppModal>
</template>

<style scoped>
.expired {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
  padding: 8px 4px 4px;
}
.expired-ic {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--warning-soft);
  color: var(--warning);
}
.expired-msg {
  margin: 0;
  color: var(--text-secondary);
}
</style>
