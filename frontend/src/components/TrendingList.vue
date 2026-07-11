<script setup lang="ts">
import { trending } from '@/mocks/data'
import Icon from './Icon.vue'

const emit = defineEmits<{ (e: 'ask', q: string): void }>()
</script>

<template>
  <ul class="trending">
    <li
      v-for="(t, i) in trending"
      :key="i"
      @click="emit('ask', t.question)"
    >
      <span class="rank" :class="{ top: i < 3 }">{{ i + 1 }}</span>
      <span class="q">{{ t.question }}</span>
      <span class="fire"><Icon name="fire" :size="13" /> {{ t.count }}</span>
    </li>
  </ul>
</template>

<style scoped>
.trending {
  list-style: none;
}
.trending li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 12px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color 0.15s ease, transform 0.12s ease;
}
.trending li:hover {
  border-color: var(--brand);
  transform: translateX(2px);
}
.rank {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.rank.top {
  background: var(--brand-soft);
  color: var(--brand);
}
.q {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.fire {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}
</style>
