<script setup lang="ts">
import Icon from './Icon.vue'

defineProps<{ citations?: number[] }>()
const emit = defineEmits<{
  (e: 'like'): void
  (e: 'dislike'): void
  (e: 'copy'): void
  (e: 'cite', id: number): void
}>()
</script>

<template>
  <div class="feedback">
    <button
      v-for="c in citations || []"
      :key="c"
      class="src-chip"
      @click="emit('cite', c)"
    >
      [{{ c }}] 来源
    </button>

    <span class="spacer" />

    <button class="fb" title="有帮助" @click="emit('like')">
      <Icon name="thumb-up" :size="15" />
    </button>
    <button class="fb" title="没帮助" @click="emit('dislike')">
      <Icon name="thumb-down" :size="15" />
    </button>
    <button class="fb" title="复制" @click="emit('copy')">
      <Icon name="copy" :size="15" />
    </button>
  </div>
</template>

<style scoped>
.feedback {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--bg-subtle);
  flex-wrap: wrap;
}
.src-chip {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  font-size: 12px;
  font-weight: 500;
  color: var(--brand);
  background: var(--chip-soft);
  border-radius: var(--radius-pill);
  transition: filter 0.15s ease;
}
.src-chip:hover {
  filter: brightness(0.97);
}
[data-theme='dark'] .src-chip:hover {
  filter: brightness(1.12);
}
.spacer {
  flex: 1;
}
.fb {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-pill);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-placeholder);
  border: 1px solid var(--bg-subtle);
  background: var(--bg-surface);
  transition: color 0.15s ease, border-color 0.15s ease, background 0.15s ease;
}
.fb:hover {
  color: var(--brand);
  border-color: var(--brand);
  background: var(--brand-soft);
}
</style>
