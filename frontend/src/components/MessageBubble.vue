<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '@/mocks/data'
import Icon from './Icon.vue'
import CitationChip from './CitationChip.vue'
import FeedbackBar from './FeedbackBar.vue'

const props = defineProps<{ message: ChatMessage }>()
const emit = defineEmits<{ (e: 'cite', id: number): void }>()

const parts = computed(() => {
  if (props.message.role !== 'assistant') return null
  const re = /\[(\d+)\]/g
  const out: { text: string; cite?: number }[] = []
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(props.message.content)) !== null) {
    if (m.index > last) out.push({ text: props.message.content.slice(last, m.index) })
    out.push({ text: m[1], cite: Number(m[1]) })
    last = re.lastIndex
  }
  if (last < props.message.content.length) out.push({ text: props.message.content.slice(last) })
  return out
})
</script>

<template>
  <!-- 用户提问：右对齐蓝色气泡 -->
  <div v-if="message.role === 'user'" class="msg user">
    <div class="bubble user-bubble">{{ message.content }}</div>
  </div>

  <!-- AI 回答：白色卡片 + 头像 + 引用 + 反馈 -->
  <div v-else class="msg assistant">
    <div class="card">
      <div class="head">
        <span class="avatar"><Icon name="sparkle" :size="15" /></span>
        <span class="name">知海 · 运营知识助手</span>
        <span class="tag">RAG 溯源</span>
      </div>

      <p class="body">
        <template v-for="(p, i) in parts" :key="i">
          <CitationChip
            v-if="p.cite"
            :index="p.cite"
            @click="emit('cite', p.cite)"
          />
          <span v-else>{{ p.text }}</span>
        </template>
      </p>

      <FeedbackBar
        :citations="message.citations"
        @cite="emit('cite', $event)"
        @like="() => {}"
        @dislike="() => {}"
        @copy="() => {}"
      />
    </div>
  </div>
</template>

<style scoped>
.msg {
  display: flex;
}
.msg.user {
  justify-content: flex-end;
}
.user-bubble {
  max-width: 560px;
  background: var(--brand);
  color: #fff;
  border-radius: 12px;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: var(--shadow-card);
}
.card {
  width: 100%;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px 20px;
  box-shadow: var(--shadow-card);
}
.head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.avatar {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.name {
  font-size: 14px;
  font-weight: 600;
}
.tag {
  font-size: 11px;
  color: var(--brand);
  background: var(--chip-soft);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  margin-left: auto;
}
.body {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
