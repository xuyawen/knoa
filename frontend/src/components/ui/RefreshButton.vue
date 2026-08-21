<script setup lang="ts">
// 全局统一刷新按钮：管理类列表页统一配置（loading 时禁用 + 图标旋转）。
import Icon from '@/components/ui/Icon.vue'
withDefaults(defineProps<{ loading?: boolean; size?: number }>(), { loading: false, size: 15 })
defineEmits<{ (e: 'click'): void }>()
</script>

<template>
  <button type="button" class="refresh-btn" title="刷新" aria-label="刷新" :disabled="loading" @click="$emit('click')">
    <Icon name="refresh" :size="size" :class="{ spin: loading }" />
  </button>
</template>

<style scoped>
.refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--dur-fast), color var(--dur-fast);
}
.refresh-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.refresh-btn:disabled { opacity: 0.5; cursor: default; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
