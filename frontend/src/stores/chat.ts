import { defineStore } from 'pinia'
import { ref } from 'vue'
import { streamAsk } from '@/api'
import type { ChatMessage, SourceItem } from '@/types/api'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const sources = ref<SourceItem[]>([])
  const streaming = ref(false)
  const sessionId = ref<string | null>(null)
  const activeSourceId = ref<number | null>(null)

  async function ask(question: string, knowledgeBase?: string | null) {
    if (streaming.value || !question.trim()) return

    // 立即显示用户消息
    messages.value.push({ id: `u-${Date.now()}`, role: 'user', content: question })
    streaming.value = true
    sources.value = []

    // 创建 assistant 占位消息
    const assistantId = `a-${Date.now()}`
    messages.value.push({
      id: assistantId,
      role: 'assistant',
      content: '',
      citations: [],
    })
    // 始终通过 reactive 数组下标取值再赋值，确保改动走 Vue 的响应式代理
    // （直接持有 push 前的本地引用会绕过代理、不触发重渲染）
    const lastMsg = () => messages.value[messages.value.length - 1]

    try {
      for await (const event of streamAsk(question, knowledgeBase, sessionId.value)) {
        const m = lastMsg()
        if (event.event === 'sources') {
          sources.value = event.data
          m.sources = event.data
        } else if (event.event === 'delta') {
          m.content += event.data.content
        } else if (event.event === 'done') {
          m.citations = event.data.citations
          sessionId.value = event.data.sessionId
        } else if (event.event === 'error') {
          m.content += `\n\n[错误] ${event.data.message}`
        }
      }
    } catch (e) {
      lastMsg().content += `\n\n[错误] ${e}`
    } finally {
      streaming.value = false
    }
  }

  function locateSource(id: number) {
    activeSourceId.value = id
    // 3 秒后自动清除高亮
    setTimeout(() => {
      if (activeSourceId.value === id) activeSourceId.value = null
    }, 3000)
  }

  function clearActiveSource() {
    activeSourceId.value = null
  }

  return { messages, sources, streaming, sessionId, activeSourceId, ask, locateSource, clearActiveSource }
})
