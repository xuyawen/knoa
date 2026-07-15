<script setup lang="ts">
import { ref } from 'vue'
import Icon from './Icon.vue'

const text = ref('')
const emit = defineEmits<{ (e: 'send', q: string): void }>()

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
        placeholder="向知海提问…（Enter 发送，Shift+Enter 换行）"
        @keydown="onKey"
        rows="1"
      />
      <div class="row">
        <button class="send" @click="send" title="发送">
          <Icon name="send" :size="18" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.composer {
  flex-shrink: 0;
  padding: 16px 24px 20px;
  background: var(--bg-page);
}
.box {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 12px 14px 10px;
  box-shadow: var(--shadow-card);
  transition: border-color 0.15s ease;
}
.box:focus-within {
  border-color: var(--brand);
}
textarea {
  width: 100%;
  display: block;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
  max-height: 120px;
}
textarea::placeholder {
  color: var(--text-placeholder);
}
.row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-top: 6px;
}
.send {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease, transform 0.12s ease;
}
.send:hover {
  background: var(--brand-hover);
}
.send:active {
  transform: scale(0.94);
}
</style>
