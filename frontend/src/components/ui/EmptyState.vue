<script setup lang="ts">
// 全局统一空状态：仅 archive 图标、无文字（视觉约定，暗色安全）。
// 需要区分尺寸时传 size（下拉/小面板用更小值）。
import Icon from '@/components/ui/Icon.vue'

withDefaults(defineProps<{ size?: number }>(), { size: 36 })
</script>

<template>
  <div class="empty-state" role="status" aria-label="暂无数据">
    <Icon name="archive" :size="size" />
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px 0;
  color: var(--text-tertiary);
  opacity: 0.6;
}
</style>
