<script setup lang="ts">

const props = defineProps<{
  id?: string | null
  name: string
  meta?: string
  alert?: boolean
}>()

const emit = defineEmits<{ (e: 'select', id: string | null): void }>()

function onClick() {
  emit('select', props.id ?? null)
}
</script>

<template>
  <button class="kc" :class="{ alert }" @click="onClick">
    <span class="nm">{{ name }}</span>
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
.nm {
  font-size: 14px;
  font-weight: 600;
}
.mt {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
