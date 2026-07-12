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
const showSteps = ref(false)  // 决策链默认收起

// 占位消息已创建但尚未收到首个 token 时，显示卡片内"正在思考"动画
const isThinking = computed(
  () => props.message.role === 'assistant' && props.message.content === '' && chat.streaming,
)

const parts = computed(() => {
  if (props.message.role !== 'assistant') return null
  // trimStart：清掉数据前导的换行/空格。否则 white-space:pre-wrap 会把 content 开头的 \n 渲染成"文字上方大量空白"
  const content = props.message.content.trimStart()
  const re = /\[(\d+)\]/g
  const out: { text: string; cite?: number }[] = []
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(content)) !== null) {
    if (m.index > last) out.push({ text: content.slice(last, m.index) })
    out.push({ text: m[1], cite: Number(m[1]) })
    last = re.lastIndex
  }
  if (last < content.length) out.push({ text: content.slice(last) })
  return out
})

function stepIcon(action: string): string {
  switch (action) {
    case 'direct_answer': return 'check'
    case 'retrieve': return 'search'
    case 'supplement_search': return 'refresh'
    default: return 'alert-circle'  // 未知/异常动作用警告图标
  }
}

/** 把内部 action 名转成用户可读的中文标签 */
function stepActionLabel(action: string): string {
  switch (action) {
    case 'direct_answer': return '直接回答'
    case 'retrieve': return '检索知识库'
    case 'supplement_search': return '补充检索'
    default: return '未知操作'
  }
}

/** 判断某个 thinking step 是否属于异常/未知动作 */
function isAbnormalStep(s: import('@/types/api').ThinkingStep): boolean {
  return !['direct_answer', 'retrieve', 'supplement_search'].includes(s.action)
}

/** 脱敏 detail 文本：把内部工具名等实现细节隐藏 */
function sanitizeDetail(detail: string): string {
  if (!detail) return ''
  // 匹配类似 "执行 xxx"、"调用 xxx" 这类包含疑似内部标识符的文本
  const internalPattern = /(?:执行|调用)\s+[a-zA-Z_][a-zA-Z0-9_]*/
  if (internalPattern.test(detail)) {
    return '系统在判断处理策略时遇到了异常状态，已自动降级为直接回答'
  }
  // 如果 detail 太长（>60字符）且包含 raw_reasoning 特征，也截断
  if (detail.length > 80) {
    return detail.slice(0, 76) + '...'
  }
  return detail
}

// 反馈闭环：点赞/点踩 + 复制
function onRate(value: 'up' | 'down') {
  chat.rateMessage(props.message.messageId, value)
}
async function onCopy() {
  try {
    await navigator.clipboard.writeText(props.message.content)
  } catch {
    /* 剪贴板不可用时静默 */
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
          <div
            v-for="(s, i) in steps"
            :key="i"
            class="step-item"
            :class="{ abnormal: isAbnormalStep(s) }"
          >
            <span class="step-num">{{ s.step }}</span>
            <Icon :name="stepIcon(s.action)" :size="13" :class="'step-icon ' + s.action" />
            <span class="step-text">
              <span class="step-action">{{ stepActionLabel(s.action) }}</span>
              <span v-if="sanitizeDetail(s.detail)" class="step-detail">{{ sanitizeDetail(s.detail) }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- 思考态：卡片内的跳动点（只要还在等 content 就显示，不因 steps 到达而消失） -->
      <div v-if="isThinking" class="thinking">
        <span class="dot" /><span class="dot" /><span class="dot" />
      </div>

      <!-- 正文 + 反馈（有内容即显示，与思考面板互不排斥） -->
      <template v-if="!isThinking">
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
          :rating="message.feedback"
          @cite="emit('cite', $event)"
          @rate="onRate"
          @copy="onCopy"
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

/* 卡片内思考动画 — 与上方 steps-toggle 内容（图标后文字）左对齐 */
.thinking {
  display: flex;
  gap: 5px;
  padding: 4px 0 4px 30px;
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
/* 未匹配到已知动作 → 警告色（异常步骤） */
.step-icon:not(.direct_answer):not(.retrieve):not(.supplement_search) {
  color: var(--warning, #f59e0b);
}
.step-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.step-action {
  font-weight: 600;
  color: var(--text-primary);
}
.step-detail {
  font-size: 11.5px;
  color: var(--text-placeholder);
  line-height: 1.35;
  white-space: normal;
  word-break: break-word;
}

/* ── 异常步骤视觉区分 ── */
.step-item.abnormal {
  background: color-mix(in srgb, var(--warning, #f59e0b) 8%, transparent);
  border-radius: 6px;
  padding: 5px 8px !important;
  margin: 2px -4px;
  border-left: 2.5px solid var(--warning, #f59e0b);
}
.step-item.abnormal .step-action {
  color: var(--warning, #f59e0b);
}
/* 收起态：完全压扁为内联行，不留任何容器空间 */
.collapsed {
  display: inline;
  background: none !important;
  padding: 0;
  margin-bottom: 0;
  border-radius: 0;
  overflow: visible;
}
.collapsed .steps-toggle {
  display: inline-flex;
  padding: 0;
}
.collapsed .steps-list { display: none; }
</style>
