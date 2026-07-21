<script setup lang="ts">
// 后端数据接口尚未接入时使用的「完整骨架页」。
// 仅做占位，不阻断菜单路由；未来接好接口后替换内容即可。
import Icon from '@/components/ui/Icon.vue'

defineProps<{
  icon?: string
  title: string
  desc?: string
  note?: string
}>()
</script>

<template>
  <div class="coming-soon card">
    <div class="cs-icon">
      <Icon :name="icon || 'grid'" :size="26" />
    </div>
    <div class="cs-title">{{ title }}</div>
    <p v-if="desc" class="cs-desc">{{ desc }}</p>
    <div class="cs-note">
      <Icon name="info" :size="13" />
      <span>{{ note || '该模块的后端数据接口尚未接入，页面骨架已就绪，菜单路由已连通。' }}</span>
    </div>
  </div>
</template>

<style scoped>
.coming-soon {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
  padding: 56px 24px;
  margin-top: 8px;
}
.cs-icon {
  width: 60px;
  height: 60px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--brand-soft);
  color: var(--brand);
  margin-bottom: 4px;
}
.cs-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}
.cs-desc {
  margin: 0;
  max-width: 460px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}
.cs-note {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 6px 14px;
  border-radius: var(--radius-pill);
  background: var(--bg-subtle);
  color: var(--text-tertiary);
  font-size: 12px;
}
.cs-note :deep(svg) { color: var(--text-tertiary); }
</style>
