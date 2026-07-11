<script setup lang="ts">
import Icon from './Icon.vue'
import ThemeToggle from './ThemeToggle.vue'

defineProps<{ title?: string; subtitle?: string }>()
const emit = defineEmits<{ (e: 'ask', q: string): void }>()
</script>

<template>
  <header class="topbar">
    <!-- 左：标题区 -->
    <div class="title-block">
      <h1 class="title">{{ title || '全部知识' }}</h1>
      <span class="subtitle">{{ subtitle || '运营知识一站式问答' }}</span>
    </div>

    <!-- 中：全局提问框 -->
    <button class="search" @click="emit('ask', '')">
      <span class="search-icon"><Icon name="search" :size="16" /></span>
      <span class="search-placeholder">向知海提问，⌘K 唤起</span>
      <kbd class="kbd">⌘K</kbd>
    </button>

    <!-- 右：操作区 -->
    <div class="actions">
      <button class="icon-btn" title="通知"><Icon name="bell" :size="18" /></button>
      <ThemeToggle />
      <div class="account" title="运营小王">运</div>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: var(--topbar-h);
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 24px;
  padding: 0 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
  flex-shrink: 0;
}
.title-block {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  min-width: 0;
  justify-self: start;
}
.title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  white-space: nowrap;
}
.subtitle {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.search {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 480px;
  max-width: 100%;
  height: 38px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  background: var(--bg-subtle);
  color: var(--text-placeholder);
  font-size: 13px;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.search:hover {
  border-color: var(--brand);
}
.search-icon {
  display: flex;
  color: var(--text-secondary);
}
.search-placeholder {
  flex: 1;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.kbd {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-family: var(--font-sans);
}
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-self: end;
}
.icon-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.icon-btn:hover {
  background: var(--brand-soft);
  color: var(--brand);
  border-color: transparent;
}
.account {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-pill);
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 13px;
}

@media (max-width: 900px) {
  .topbar {
    display: none;
  }
}
</style>
