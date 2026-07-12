<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '@/types/api'
import { useChatStore } from '@/stores/chat'
import Icon from './Icon.vue'
import CitationChip from './CitationChip.vue'
import FeedbackBar from './FeedbackBar.vue'

const props = defineProps<{ message: ChatMessage }>()
const emit = defineEmits<{ (e: 'cite', id: number): void }>()

const chat = useChatStore()

// 占位消息已创建但尚未收到首个 token 时，显示卡片内"正在思考"动画
const isThinking = computed(
  () => props.message.role === 'assistant' && props.message.content === '' && chat.streaming,
)

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
        <span v-if="(message as any).sources?.length" class="tag">
          <span class="tag-dot" />
          RAG 溯源
        </span>
      </div>

      <!-- 思考态：卡片内的跳动点 -->
      <div v-if="isThinking" class="thinking">
        <span class="dot" /><span class="dot" /><span class="dot" />
      </div>

      <!-- 正文 + 反馈 -->
      <template v-else>
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
      </template>
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

/* 渐变描边 + 微弱悬浮 + 阴影，拉开与背景的层次 */
.card {
  width: 100%;
  border: 1px solid transparent;
  border-radius: var(--radius-lg);
  padding: 16px 20px;
  background:
    linear-gradient(var(--bg-surface), var(--bg-surface)) padding-box,
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--brand) 22%, transparent),
      color-mix(in srgb, var(--brand) 5%, transparent)
    ) border-box;
  box-shadow: var(--shadow-card);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.card:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-float);
}

.head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
/* 头像外圈光晕，强化品牌识别 */
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
  box-shadow: 0 0 0 3px var(--brand-soft);
}
.name {
  font-size: 14px;
  font-weight: 600;
}
.tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--brand);
  background: var(--chip-soft);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  margin-left: auto;
  font-weight: 500;
}
.tag-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--brand);
}

.body {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

/* 卡片内思考动画，品牌色跳动点 */
.thinking {
  display: flex;
  gap: 5px;
  padding: 6px 2px;
}
.thinking .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--brand);
  opacity: 0.3;
  animation: think 1.2s infinite;
}
.thinking .dot:nth-child(2) {
  animation-delay: 0.2s;
}
.thinking .dot:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes think {
  0%, 60%, 100% {
    opacity: 0.3;
    transform: translateY(0);
  }
  30% {
    opacity: 1;
    transform: translateY(-5px);
  }
}
</style>
