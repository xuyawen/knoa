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
    // 取回 reactive 代理再赋值：push 进数组的是原始对象，
    // 若直接改本地引用不会触发重渲染，必须走代理
    const msg = messages.value[messages.value.length - 1]

    try {
      for await (const event of streamAsk(question, knowledgeBase, sessionId.value)) {
        if (event.event === 'sources') {
          sources.value = event.data
          msg.sources = event.data
        } else if (event.event === 'delta') {
          msg.content += event.data.content
        } else if (event.event === 'done') {
          msg.citations = event.data.citations
          sessionId.value = event.data.sessionId
        } else if (event.event === 'error') {
          msg.content += `\n\n[错误] ${event.data.message}`
        }
      }
    } catch (e) {
      msg.content += `\n\n[错误] ${e}`
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
