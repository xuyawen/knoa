<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  id?: string | null
  name: string
  meta?: string
  alert?: boolean
  healthScore?: number
}>()

const emit = defineEmits<{ (e: 'select', id: string | null): void }>()

function onClick() {
  emit('select', props.id ?? null)
}

/** 圆点颜色，与 AppSidebar / HealthBar 保持一致 */
const dotColor = computed(() => {
  const s = props.healthScore
  if (s == null || s === 0) return '#aab2c2'
  if (s < 0.6) return 'var(--danger)'
  if (s < 0.85) return 'var(--warning)'
  return 'var(--success)'
})
</script>

<template>
  <button class="kc" :class="{ alert }" @click="onClick">
    <span class="kc-header">
      <span class="kc-dot" :style="{ '--dot-color': dotColor }"></span>
      <span class="nm">{{ name }}</span>
    </span>
    <span v-if="meta" class="mt">{{ meta }}</span>
  </button>
</template>

<style scoped>
.kc {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
  text-align: left;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px;
  min-height: 72px;
  transition: border-color 0.15s ease, transform 0.12s ease;
}
.kc:hover {
  border-color: var(--brand);
  transform: translateY(-2px);
}
.kc-header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.kc-dot {
  position: relative;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--dot-color);
  flex-shrink: 0;
}
.kc-dot::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  background: var(--dot-color);
  opacity: 0.3;
  filter: blur(3px);
}
.nm {
  font-size: 14px;
  font-weight: 600;
}
.mt {
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: 20px; /* 缩进对齐标题文字 */
}
</style>
