<script setup lang="ts">
import { ref, computed } from 'vue'
import Icon from './Icon.vue'

const text = ref('')
const emit = defineEmits<{ (e: 'send', q: string): void }>()

const placeholder = computed(() =>
  window.innerWidth < 640 ? '向知海提问…' : '向知海提问…（Enter 发送，Shift+Enter 换行）'
)

function send() {
  const q = text.value.trim()
  if (!q) return
  emit('send', q)
  text.value = ''
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}
</script>

<template>
  <div class="composer">
    <div class="box">
      <textarea
        v-model="text"
        :placeholder="placeholder"
        @keydown="onKey"
        rows="3"
      />
      <button class="send" @click="send" title="发送" :disabled="!text.trim()">
        <Icon name="send" :size="18" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.composer {
  flex-shrink: 0;
  padding: 12px 16px 16px;
  background: var(--bg-page);
}
.box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 10px 10px 10px 14px;
  box-shadow: var(--shadow-card);
  transition: border-color 0.15s ease;
}
.box:focus-within {
  border-color: var(--brand);
}
textarea {
  flex: 1;
  min-width: 0;
  display: block;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
  min-height: 63px;
  max-height: 100px;
}
textarea::placeholder {
  color: var(--text-placeholder);
}
.send {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.12s ease, opacity 0.15s ease;
}
.send:hover:not(:disabled) {
  background: var(--brand-hover);
}
.send:active:not(:disabled) {
  transform: scale(0.94);
}
.send:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
