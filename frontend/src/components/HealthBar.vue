<script setup lang="ts">
import type { HealthItem } from '@/types/api'
import Icon from './Icon.vue'

defineProps<{ item: HealthItem }>()
</script>

<template>
  <div class="card" :class="{ alert: item.kb === '合规库' }">
    <div class="icon">
      <Icon v-if="item.kb === '合规库'" name="compliance" :size="15" />
      <Icon v-else-if="item.kb === '广告投放'" name="ads" :size="15" />
      <Icon v-else-if="item.kb === '物流仓储'" name="logistics" :size="15" />
      <Icon v-else name="library" :size="15" />
    </div>
    <div class="name">{{ item.kb }}</div>
    <div class="count">{{ item.docCount }}<span>篇</span></div>
    <div class="bar">
      <div class="fill" :style="{ width: item.coverage * 100 + '%' }" />
    </div>
    <div class="cov">{{ Math.round(item.coverage * 100) }}% 覆盖</div>
  </div>
</template>

<style scoped>
.card {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.card.alert {
  background: var(--danger-soft);
  border-color: transparent;
}
.icon {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: var(--bg-surface);
  color: var(--brand);
  display: flex;
  align-items: center;
  justify-content: center;
}
.card.alert .icon {
  background: #fff;
  color: var(--danger);
}
.name {
  font-size: 12px;
  font-weight: 500;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.count {
  font-size: 16px;
  font-weight: 600;
  font-family: var(--font-display);
}
.count span {
  font-size: 11px;
  font-weight: 400;
  color: var(--text-secondary);
  margin-left: 2px;
}
.bar {
  height: 5px;
  border-radius: var(--radius-pill);
  background: var(--bg-surface);
  overflow: hidden;
  margin-top: 2px;
}
.card.alert .bar {
  background: rgba(255, 255, 255, 0.6);
}
.fill {
  height: 100%;
  border-radius: var(--radius-pill);
  background: var(--brand);
}
.card.alert .fill {
  background: var(--danger);
}
.cov {
  font-size: 11px;
  color: var(--text-secondary);
}
</style>
