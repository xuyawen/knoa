<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ChatMessage } from '@/types/api'
import { useChatStore } from '@/stores/chat'
import Icon from './Icon.vue'
import CitationChip from './CitationChip.vue'
import FeedbackBar from './FeedbackBar.vue'

const props = defineProps<{ message: ChatMessage }>()
const emit = defineEmits<{ (e: 'cite', id: number): void }>()

const chat = useChatStore()

// Agent 决策步骤（Agentic RAG thinking events）
const steps = computed(() => (props.message.thinkingSteps || []) as import('@/types/api').ThinkingStep[])
const showSteps = ref(true)  // 决策链默认展开

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

function stepIcon(action: string): string {
  switch (action) {
    case 'direct_answer': return 'check'
    case 'retrieve': return 'search'
    case 'supplement_search': return 'refresh'
    default: return 'sparkle'
  }
}
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

      <!-- Agent 决策链（Agentic RAG thinking steps） -->
      <div v-if="steps.length" class="agent-steps" :class="{ collapsed: !showSteps }">
        <button class="steps-toggle" @click="showSteps = !showSteps">
          <Icon name="sparkle" :size="12" />
          <span>思考过程 ({{ steps.length }}步)</span>
          <Icon :name="showSteps ? 'chevron-down' : 'chevron-right'" :size="12" />
        </button>
        <div v-show="showSteps" class="steps-list">
          <div v-for="(s, i) in steps" :key="i" class="step-item">
            <span class="step-num">{{ s.step }}</span>
            <Icon :name="stepIcon(s.action)" :size="13" :class="'step-icon ' + s.action" />
            <span class="step-text">{{ s.detail }}</span>
          </div>
        </div>
      </div>

      <!-- 思考态：卡片内的跳动点 -->
      <div v-else-if="isThinking" class="thinking">
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

/* ── Agent 决策链 (Agentic RAG thinking steps) ── */
.agent-steps {
  margin-bottom: 12px;
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--brand) 4%, transparent);
  overflow: hidden;
  transition: all 0.2s ease;
}
.steps-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-secondary);
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.15s ease;
}
.steps-toggle:hover {
  color: var(--brand);
}
.steps-list {
  padding: 0 12px 10px;
}
.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.4;
}
.step-num {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--bg-subtle);
  color: var(--text-placeholder);
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.step-icon { flex-shrink: 0; }
.step-icon.direct_answer { color: #22c55e; }   /* 绿：直接答 */
.step-icon.retrieve { color: var(--brand); }     /* 蓝：检索 */
.step-icon.supplement_search { color: #f59e0b; } /* 橙：补检 */
.step-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 收起态 */
.collapsed .steps-list { display: none; }
</style>
