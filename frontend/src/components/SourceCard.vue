<script setup lang="ts">
import type { SourceItem } from '@/mocks/data'
import Icon from './Icon.vue'

defineProps<{ source: SourceItem }>()
const emit = defineEmits<{ (e: 'locate', id: number): void }>()
</script>

<template>
  <button class="card" @click="emit('locate', source.id)">
    <div class="head">
      <span class="kb">{{ source.kb }}</span>
      <span class="conf" :class="{ low: source.confidence < 0.9 }">
        {{ Math.round(source.confidence * 100) }}%
      </span>
    </div>
    <div class="title">{{ source.title }}</div>
    <div class="snippet">{{ source.snippet }}</div>
    <div class="foot">
      <span class="loc">查看溯源</span>
      <Icon name="external" :size="13" />
    </div>
  </button>
</template>

<style scoped>
.card {
  display: block;
  width: 100%;
  text-align: left;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  margin-bottom: 10px;
  transition: border-color 0.15s ease, transform 0.12s ease;
}
.card:hover {
  border-color: var(--brand);
  transform: translateY(-1px);
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.kb {
  font-size: 12px;
  color: var(--brand);
  font-weight: 500;
}
.conf {
  font-size: 12px;
  color: var(--success);
  font-weight: 600;
}
.conf.low {
  color: var(--danger);
}
.title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
  line-height: 1.4;
}
.snippet {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.foot {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--brand);
}
</style>
