<script setup lang="ts">
import Icon from './Icon.vue'

const tabs = [
  { key: 'home', label: '首页', icon: 'home' },
  { key: 'kb', label: '知识库', icon: 'library' },
  { key: 'chat', label: '问答', icon: 'chat' },
  { key: 'me', label: '我的', icon: 'user' },
]
const active = defineModel<string>({ default: 'home' })
</script>

<template>
  <nav class="mnav">
    <button
      v-for="t in tabs"
      :key="t.key"
      class="tab"
      :class="{ active: t.key === active }"
      @click="active = t.key"
    >
      <Icon :name="t.icon" :size="20" />
      <span>{{ t.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.mnav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: calc(62px + env(safe-area-inset-bottom));
  display: flex;
  background: var(--bg-surface);
  border-top: 1px solid var(--border);
  padding-bottom: env(safe-area-inset-bottom);
  z-index: 30;
}
.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  color: var(--text-secondary);
  font-size: 11px;
  transition: color 0.15s ease;
}
.tab.active {
  color: var(--brand);
}
.tab svg {
  color: var(--text-secondary);
  transition: color 0.15s ease;
}
.tab.active svg {
  color: var(--brand);
}
</style>
