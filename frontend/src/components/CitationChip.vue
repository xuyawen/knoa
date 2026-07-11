<script setup lang="ts">
defineProps<{ index: number }>()
const emit = defineEmits<{ (e: 'click', id: number): void }>()
</script>

<template>
  <button class="cite" @click="emit('click', index)" :title="`查看来源 ${index}`">
    [{{ index }}]
  </button>
</template>

<style scoped>
.cite {
  display: inline-flex;
  align-items: center;
  margin: 0 2px;
  padding: 0 6px;
  height: 18px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  color: var(--brand);
  background: var(--chip-soft);
  border-radius: var(--radius-pill);
  vertical-align: baseline;
  transition: filter 0.15s ease;
}
.cite:hover {
  filter: brightness(0.96);
}
[data-theme='dark'] .cite:hover {
  filter: brightness(1.15);
}
</style>
