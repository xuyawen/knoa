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
    const assistantMsg: ChatMessage = {
      id: `a-${Date.now()}`,
      role: 'assistant',
      content: '',
      citations: [],
    }
    messages.value.push(assistantMsg)

    try {
      for await (const event of streamAsk(question, knowledgeBase, sessionId.value)) {
        if (event.event === 'sources') {
          sources.value = event.data
          assistantMsg.sources = event.data
        } else if (event.event === 'delta') {
          assistantMsg.content += event.data.content
        } else if (event.event === 'done') {
          assistantMsg.citations = event.data.citations
          sessionId.value = event.data.sessionId
        } else if (event.event === 'error') {
          assistantMsg.content += `\n\n[错误] ${event.data.message}`
        }
      }
    } catch (e) {
      assistantMsg.content += `\n\n[错误] ${e}`
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
