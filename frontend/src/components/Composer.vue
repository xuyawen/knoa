<script setup lang="ts">
import { ref, computed } from 'vue'
import Icon from './Icon.vue'
import type { ChatAttachment } from '@/types/api'

const text = ref('')
const attachments = ref<ChatAttachment[]>([])
const fileInput = ref<HTMLInputElement | null>(null)

const emit = defineEmits<{ (e: 'send', payload: { text: string; files: ChatAttachment[] }): void }>()

const placeholder = computed(() =>
  window.innerWidth < 640 ? '向知海提问…' : '向知海提问…（Enter 发送，Shift+Enter 换行，可附图片）'
)

// 单张图片上限：base64 会膨胀约 33%，过大塞进请求/DB 不划算
const MAX_FILE_MB = 8
const MAX_FILES = 4

function pickFiles() {
  fileInput.value?.click()
}

function onFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  for (const f of files) {
    if (!f.type.startsWith('image/')) continue
    if (f.size > MAX_FILE_MB * 1024 * 1024) {
      alert(`图片「${f.name}」超过 ${MAX_FILE_MB}MB，已跳过`)
      continue
    }
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      const meta = result.slice(0, result.indexOf(','))
      const mime = meta.replace('data:', '').replace(/;.*$/, '')
      const b64 = result.slice(result.indexOf(',') + 1)
      attachments.value.push({ kind: 'image', mimeType: mime, dataB64: b64, name: f.name })
    }
    reader.readAsDataURL(f)
  }
  input.value = '' // 允许重复选择同一文件
}

function removeAttachment(idx: number) {
  attachments.value.splice(idx, 1)
}

function send() {
  const q = text.value.trim()
  if (!q && !attachments.value.length) return
  emit('send', { text: q, files: attachments.value })
  text.value = ''
  attachments.value = []
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
    <!-- 附件预览：图片缩略图 + 移除 -->
    <div v-if="attachments.length" class="attachments">
      <div v-for="(a, i) in attachments" :key="i" class="att-chip">
        <img :src="`data:${a.mimeType};base64,${a.dataB64}`" class="att-thumb" alt="" />
        <button class="att-remove" @click="removeAttachment(i)" title="移除">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
    </div>

    <div class="box">
      <button
        class="attach-btn"
        @click="pickFiles"
        title="上传图片"
        :disabled="attachments.length >= MAX_FILES"
      >
        <Icon name="paperclip" :size="18" />
      </button>
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        multiple
        hidden
        @change="onFiles"
      />
      <textarea
        v-model="text"
        :placeholder="placeholder"
        @keydown="onKey"
        rows="3"
      />
      <button class="send" @click="send" title="发送" :disabled="!text.trim() && !attachments.length">
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
.attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
.att-chip {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--bg-surface);
}
.att-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.att-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}
.att-remove:hover {
  background: rgba(0, 0, 0, 0.75);
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
.attach-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: var(--text-placeholder);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}
.attach-btn:hover:not(:disabled) {
  color: var(--brand);
  background: var(--brand-soft);
}
.attach-btn:disabled {
  opacity: 0.35;
  cursor: default;
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
