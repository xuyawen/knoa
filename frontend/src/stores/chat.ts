import { defineStore, acceptHMRUpdate } from 'pinia'
import { ref } from 'vue'
import {
  streamAsk,
  submitFeedback,
  deleteFeedback,
  getSourceDetail,
  getSessions,
  getSession,
  createSession,
  deleteSession,
  batchDeleteSessions,
} from '@/api'
import type { ChatMessage, ChatAttachment, SourceItem, SourceDetail, ChatSession } from '@/types/api'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const sources = ref<SourceItem[]>([])
  const streaming = ref(false)
  const sessionId = ref<string | null>(null)
  const activeSourceId = ref<number | null>(null)
  const activeSourceDetail = ref<SourceDetail | null>(null)
  const loadingSource = ref(false)
  const sessions = ref<ChatSession[]>([])
  const historyOpen = ref(false)
  const loadingHistory = ref(false)

  // 独立的知识域筛选（聊天头部下拉选择器控制）。
  // 与 knowledge.activeBase（侧边栏选中/页面上下文库）解耦，
  // 这样切筛选不会改变 TopBar 标题。
  const filterKb = ref<string | null>(null)

  async function ask(question: string, knowledgeBase?: string | null, files?: ChatAttachment[]) {
    if (streaming.value || (!question.trim() && !files?.length)) return

    // 立即显示用户消息（含多模态附件）
    messages.value.push({ id: `u-${Date.now()}`, role: 'user', content: question, attachments: files ?? [] })
    streaming.value = true
    sources.value = []

    // 创建 assistant 占位消息
    const assistantId = `a-${Date.now()}`
    messages.value.push({
      id: assistantId,
      role: 'assistant',
      content: '',
      citations: [],
      thinkingSteps: [],
    })
    // 始终通过 reactive 数组下标取值再赋值，确保改动走 Vue 的响应式代理
    // （直接持有 push 前的本地引用会绕过代理、不触发重渲染）
    const lastMsg = () => messages.value[messages.value.length - 1]

    try {
      for await (const event of streamAsk(question, knowledgeBase, sessionId.value, files)) {
        const m = lastMsg()
        if (event.event === 'thinking') {
          // Agent 决策步骤：追加到当前消息的思考链
          if (!m.thinkingSteps) m.thinkingSteps = []
          m.thinkingSteps.push(event.data)
        } else if (event.event === 'sources') {
          sources.value = event.data
          m.sources = event.data
        } else if (event.event === 'delta') {
          m.content += event.data.content
        } else if (event.event === 'done') {
          m.citations = event.data.citations
          m.messageId = event.data.messageId
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

  async function openSource(chunkId: string) {
    loadingSource.value = true
    try {
      activeSourceDetail.value = await getSourceDetail(chunkId)
    } catch (e) {
      console.error('加载溯源详情失败', e)
    } finally {
      loadingSource.value = false
    }
  }

  function closeSourceDetail() {
    activeSourceDetail.value = null
  }

  // ── 多会话历史 ──
  async function loadSessions() {
    loadingHistory.value = true
    try {
      sessions.value = await getSessions()
    } catch (e) {
      console.error('加载会话列表失败', e)
    } finally {
      loadingHistory.value = false
    }
  }

  function toggleHistory() {
    historyOpen.value = !historyOpen.value
    if (historyOpen.value) loadSessions()
  }

  function closeHistory() {
    historyOpen.value = false
  }

  async function startNewChat() {
    try {
      const s = await createSession()
      sessionId.value = s.id
    } catch (e) {
      console.error('新建会话失败', e)
    }
    messages.value = []
    sources.value = []
    historyOpen.value = false
  }

  async function switchSession(id: string) {
    loadingHistory.value = true
    try {
      const detail = await getSession(id)
      sessionId.value = detail.id
      messages.value = detail.messages.map((m, i) => ({
        id: `h-${i}-${m.role}`,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        citations: m.citations ?? [],
        sources: m.sources ?? [],
        attachments: (m.attachments ?? []) as ChatAttachment[],
        thinkingSteps: [],
        feedback: null,
      }))
      // 汇总所有消息的 sources, 让历史回答里的引用能定位
      const all: SourceItem[] = []
      for (const m of detail.messages) {
        if (m.sources) all.push(...m.sources)
      }
      sources.value = all
      historyOpen.value = false
    } catch (e) {
      console.error('切换会话失败', e)
    } finally {
      loadingHistory.value = false
    }
  }

  /** 删除单个会话（本地移除 + 远端删除）。 */
  async function removeSession(id: string) {
    try {
      await deleteSession(id)
      sessions.value = sessions.value.filter((s) => s.id !== id)
      // 若删的是当前活跃会话，重置到空白
      if (sessionId.value === id) {
        startNewChat()
      }
    } catch (e) {
      console.error('删除会话失败', e)
      throw e
    }
  }

  /** 批量删除会话。 */
  async function removeSessions(ids: string[]) {
    try {
      await batchDeleteSessions(ids)
      sessions.value = sessions.value.filter((s) => !ids.includes(s.id))
      if (ids.includes(sessionId.value!)) {
        startNewChat()
      }
    } catch (e) {
      console.error('批量删除会话失败', e)
      throw e
    }
  }

  // 反馈闭环：乐观更新本地状态 + 调接口（upsert / 取消）
  async function rateMessage(messageId: string | undefined, rating: 'up' | 'down') {
    if (!messageId) return
    const msg = messages.value.find((m) => m.messageId === messageId)
    if (!msg) return
    // 点同一个 = 取消
    const next: 'up' | 'down' | null = msg.feedback === rating ? null : rating
    msg.feedback = next
    try {
      if (next) await submitFeedback(messageId, next)
      else await deleteFeedback(messageId)
    } catch {
      // 接口失败不影响本地体验，静默
    }
  }

  return { messages, sources, streaming, sessionId, activeSourceId,
    activeSourceDetail, loadingSource,
    sessions, historyOpen, loadingHistory,
    filterKb,
    ask, locateSource, clearActiveSource, openSource, closeSourceDetail,
    loadSessions, toggleHistory, closeHistory, startNewChat, switchSession,
    removeSession, removeSessions,
    rateMessage }
})

// 支持 Pinia store 热更新（否则改 store 文件后 live 实例不会刷新，导致方法缺失）
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useChatStore, import.meta.hot))
}
