<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import type { SourceDetail } from '@/types/api'

defineProps<{ detail: SourceDetail | null; loading: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div v-if="detail || loading" class="overlay" @click.self="emit('close')">
      <aside class="drawer">
        <header class="d-head">
          <div class="d-head-text">
            <span class="d-kb">{{ detail?.kb }}</span>
            <h3 class="d-title">{{ detail?.title }}</h3>
          </div>
          <button class="d-close" title="关闭" @click="emit('close')">×</button>
        </header>
        <div class="d-body">
          <div v-if="loading" class="d-loading">加载中…</div>
          <template v-else-if="detail">
            <pre class="d-content">{{ detail.content }}</pre>
            <div class="d-foot">片段 #{{ detail.chunkIndex + 1 }}</div>
          </template>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(2px);
  z-index: 60;
  display: flex;
  justify-content: flex-end;
  animation: fade 0.18s ease;
}
.drawer {
  width: min(520px, 92vw);
  height: 100%;
  background: var(--bg-surface);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-float);
  animation: slide 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}
.d-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
}
.d-head-text {
  min-width: 0;
}
.d-kb {
  font-size: 12px;
  color: var(--brand);
  font-weight: 500;
}
.d-title {
  font-size: 16px;
  font-weight: 600;
  margin-top: 4px;
  line-height: 1.35;
}
.d-close {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 20px;
  line-height: 1;
  transition: background 0.15s ease;
}
.d-close:hover {
  background: var(--bg-subtle);
  color: var(--text-primary);
}
.d-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 20px;
}
.d-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-mono, monospace);
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-primary);
  margin: 0;
}
.d-foot {
  margin-top: 14px;
  font-size: 11px;
  color: var(--text-placeholder);
}
.d-loading {
  color: var(--text-placeholder);
  font-size: 13px;
}
@keyframes fade {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes slide {
  from { transform: translateX(24px); opacity: 0.6; }
  to { transform: translateX(0); opacity: 1; }
}
</style>
