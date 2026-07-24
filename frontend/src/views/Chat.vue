<script setup lang="ts">
// 智能问答 — 对话主界面，接真实 SSE 流式问答。
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'
import {
  getSessions,
  createSession,
  getSession,
  deleteSession,
  streamAsk,
  submitFeedback,
  deleteFeedback,
  ttsSpeak,
  getDocument,
} from '@/api'
import type {
  ChatSession,
  ChatMessage,
  SessionMessage,
  ThinkingStep,
  SourceItem,
  ChatAttachment,
  Paginated,
  DocumentDetail,
} from '@/types/api'
import { uploadToOss } from '@/utils/oss'
import { useModelConfig } from '@/composables/useModelConfig'

// 读取模型配置（单一真值在 /api/settings 服务端，经 useModelConfig 单例缓存）。
// 拼成后端 AskRequest 接受的字段随每次问答下发。空值不传，走后端默认。
function readModelConfig(): Record<string, unknown> {
  const cfg: Record<string, unknown> = {}
  if (state.preferredModel) cfg.model = state.preferredModel
  if (state.prefs.temp != null) cfg.temperature = Number(state.prefs.temp)
  if (state.prefs.topP != null) cfg.topP = Number(state.prefs.topP)
  if (state.prefs.maxTokens != null) cfg.maxTokens = Number(state.prefs.maxTokens)
  if (state.prefs.topK != null) cfg.topK = Number(state.prefs.topK)
  if (state.prefs.sourceCount != null) cfg.sourceCount = Number(state.prefs.sourceCount)
  if (state.prefs.webProvider != null) cfg.webProvider = state.prefs.webProvider
  if (state.prefs.webSearch != null) cfg.webSearch = Boolean(state.prefs.webSearch)
  if (state.prefs.systemPrompt) cfg.systemPrompt = state.prefs.systemPrompt
  if (state.prefs.conciseMode != null) cfg.conciseMode = Boolean(state.prefs.conciseMode)
  return cfg
}

const toast = useToastStore()
const auth = useAuthStore()
// 模型配置单一真值在服务端；单例加载一次，与 ModelConfig 页共享
const { state, load } = useModelConfig()
load()

// 语音播报（P8）：朗读某条 AI 回答
const playingId = ref<string | null>(null)
let audioEl: HTMLAudioElement | null = null
async function speak(m: ChatMessage) {
  if (!m.content || playingId.value) return
  playingId.value = m.id
  try {
    const { audio, contentType } = await ttsSpeak(m.content)
    audioEl = new Audio(`data:${contentType};base64,${audio}`)
    audioEl.onended = () => { playingId.value = null; audioEl = null }
    await audioEl.play()
  } catch (e) {
    playingId.value = null
    toast.error(e instanceof Error ? e.message : '语音播报失败')
  }
}

// 从「问答记录」打开某会话：载入消息并切回对话视图

const sessionsData = ref<Paginated<ChatSession> | null>(null)
const sessions = ref<ChatSession[]>([])
const sessionPage = ref(1)
const SESSION_PAGE_SIZE = 20
const sessionLoadingMore = ref(false)
const allSessionsLoaded = ref(false)
const sessionTotal = ref(0)

const activeId = ref<string | null>(null)
const deleteTargetId = ref<string | null>(null)
const showClearConfirm = ref(false)
const messages = ref<ChatMessage[]>([])
const streaming = ref(false)
const inputText = ref('')
const errorMsg = ref('')
const askAbort = ref<AbortController | null>(null)
const attached = ref<ChatAttachment[]>([])
const expandedThinking = ref<Set<string>>(new Set())
function toggleThinking(id: string) {
  const next = new Set(expandedThinking.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedThinking.value = next
}

// 组件卸载时清理进行中的问答流与 TTS 音频，避免对已销毁实例继续回调/播放
onBeforeUnmount(() => {
  askAbort.value?.abort()
  if (audioEl) {
    audioEl.pause()
    audioEl = null
  }
})

// 文档详情弹框
const docDetail = ref<DocumentDetail | null>(null)
const docDetailLoading = ref(false)
const detail = computed(() => docDetail.value!)
async function openDocDetail(s: SourceItem) {
  // 联网来源：有链接则新窗口打开
  if (s.sourceType === 'web' && s.url) {
    window.open(s.url, '_blank', 'noopener,noreferrer')
    return
  }
  // 知识库来源：必须有 kbId + docId 才能查文档详情
  if (s.sourceType !== 'kb' || !s.kbId || !s.docId) {
    toast.warning(s.sourceType === 'kb' ? '该引用缺少文档标识，无法查看详情' : '仅知识库来源支持查看文档详情')
    return
  }
  docDetailLoading.value = true
  docDetail.value = null
  try {
    docDetail.value = await getDocument(s.kbId, s.docId)
  } catch (e: any) {
    toast.error(`加载文档失败：${e?.message || e}`)
  } finally {
    docDetailLoading.value = false
  }
}

const scrollRef = ref<HTMLElement | null>(null)

const activeSession = computed(() => sessions.value.find((s) => s.id === activeId.value) || null)
const firstQuestion = computed(() => {
  const u = messages.value.find((m) => m.role === 'user')
  return u?.content || activeSession.value?.title || ''
})

const suggested = [
  '差旅报销需要哪些材料？',
  '差旅报销的标准是怎么样的？',
  '如何申请系统权限？',
  '员工入职流程是怎样的？',
]

/* ---------- 工具 ---------- */
function scrollToBottom() {
  nextTick(() => {
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function readFileB64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => {
      const res = r.result as string
      const comma = res.indexOf(',')
      resolve(comma >= 0 ? res.slice(comma + 1) : res)
    }
    r.onerror = () => reject(r.error)
    r.readAsDataURL(file)
  })
}

/** 多模态附件 → data URI（图片/音频/视频统一用 base64 内联播放或预览）。 */
function attachSrc(a: { mimeType?: string; dataB64?: string }): string {
  return `data:${a.mimeType};base64,${a.dataB64}`
}

/** 由 MIME 推断附件种类，决定缩略图/播放器渲染。 */
function kindOf(file: File): 'image' | 'audio' | 'video' | null {
  if (file.type.startsWith('image/')) return 'image'
  if (file.type.startsWith('audio/')) return 'audio'
  if (file.type.startsWith('video/')) return 'video'
  return null
}

/** 复制 AI 回答到剪贴板。 */
async function copyAnswer(m: ChatMessage) {
  if (!m.content) return
  try {
    await navigator.clipboard.writeText(m.content)
    toast.success('已复制回答')
  } catch {
    toast.error('复制失败，请手动选择')
  }
}

/** 格式化文件大小。 */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function toChatMessage(m: SessionMessage): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role: m.role === 'assistant' ? 'assistant' : 'user',
    content: m.content,
    citations: m.citations || undefined,
    sources: m.sources || undefined,
    attachments: m.attachments || null,
    thinkingSteps: undefined,
    feedback: null,
  }
}

/* ---------- 会话（懒加载） ---------- */
const convListRef = ref<HTMLElement | null>(null)

async function loadSessions(append = false) {
  if (sessionLoadingMore.value || allSessionsLoaded.value) return
  const page = append ? sessionPage.value + 1 : 1
  try {
    if (append) sessionLoadingMore.value = true
    const data = await getSessions(page, SESSION_PAGE_SIZE)
    sessionsData.value = data
    sessionTotal.value = data.total
    sessionPage.value = page
    if (append) {
      sessions.value.push(...data.items)
    } else {
      sessions.value = [...data.items]
    }
    // 检查是否还有更多
    allSessionsLoaded.value = data.items.length < SESSION_PAGE_SIZE || sessions.value.length >= data.total
  } catch (e: any) {
    toast.error(`加载会话失败：${e?.message || e}`)
  } finally {
    sessionLoadingMore.value = false
  }
}

/** 滚动到底部自动加载 */
function onConvScroll(e: Event) {
  const el = e.target as HTMLElement
  if (!el || sessionLoadingMore.value || allSessionsLoaded.value) return
  const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
  if (nearBottom) loadSessions(true)
}

async function selectSession(id: string) {
  askAbort.value?.abort()
  streaming.value = false
  activeId.value = id
  errorMsg.value = ''
  try {
    const det = await getSession(id)
    messages.value = det.messages.map(toChatMessage)
    scrollToBottom()
  } catch (e: any) {
    toast.error(`加载会话失败：${e?.message || e}`)
  }
}

async function newChat() {
  askAbort.value?.abort()
  streaming.value = false
  try {
    const s = await createSession()
    activeId.value = s.id
    messages.value = []
    errorMsg.value = ''
    await loadSessions()
  } catch (e: any) {
    toast.error(`新建会话失败：${e?.message || e}`)
  }
}

function onDeleteSession(id: string) {
  deleteTargetId.value = id
}

async function confirmDeleteSession() {
  if (!deleteTargetId.value) return
  try {
    await deleteSession(deleteTargetId.value)
    if (activeId.value === deleteTargetId.value) {
      activeId.value = null
      messages.value = []
    }
    await loadSessions()
    toast.success('会话已删除')
  } catch (e: any) {
    toast.error(`删除失败：${e?.message || e}`)
  } finally {
    deleteTargetId.value = null
  }
}

/* ---------- 清空对话 ---------- */
function confirmClear() {
  messages.value = []
  inputText.value = ''
  showClearConfirm.value = false
  toast.success('对话已清空')
}

/* ---------- 发送（SSE） ---------- */
async function send() {
  const text = inputText.value.trim()
  if (!text || streaming.value) return

  let sid = activeId.value
  if (!sid) {
    try {
      const s = await createSession()
      sid = s.id
      const cur = sessionsData.value
      sessionsData.value = cur
        ? { ...cur, items: [s, ...cur.items], total: cur.total + 1 }
        : { items: [s], total: 1, page: 1, pageSize: 20, pages: 1 }
      activeId.value = sid
    } catch (e: any) {
      toast.error(`创建会话失败：${e?.message || e}`)
      return
    }
  }

  const userMsg: ChatMessage = {
    id: crypto.randomUUID(),
    role: 'user',
    content: text,
    attachments: attached.value.length ? [...attached.value] : null,
    feedback: null,
  }
  const aiMsg: ChatMessage = {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '',
    thinkingSteps: [],
    feedback: null,
  }
  messages.value.push(userMsg, aiMsg)
  inputText.value = ''
  attached.value = []
  scrollToBottom()

  streaming.value = true
  errorMsg.value = ''
  const ac = new AbortController()
  askAbort.value = ac

  try {
    for await (const ev of streamAsk(text, null, sid, userMsg.attachments || undefined, {
      signal: ac.signal,
      modelConfig: readModelConfig(),
    })) {
      if (ev.event === 'thinking') {
        aiMsg.thinkingSteps = [...(aiMsg.thinkingSteps || []), ev.data as ThinkingStep]
      } else if (ev.event === 'sources') {
        aiMsg.sources = ev.data as SourceItem[]
      } else if (ev.event === 'delta') {
        aiMsg.content += (ev.data as { content: string }).content
        scrollToBottom()
      } else if (ev.event === 'done') {
        const d = ev.data as { messageId: string; sessionId: string }
        aiMsg.messageId = d.messageId
        if (d.sessionId) activeId.value = d.sessionId
      } else if (ev.event === 'error') {
        const d = ev.data as { message: string }
        errorMsg.value = d.message
        toast.error(`问答出错：${d.message}`)
      }
    }
  } catch (e: any) {
    if (e?.name !== 'AbortError') {
      toast.error(`问答中断：${e?.message || e}`)
    }
  } finally {
    streaming.value = false
    askAbort.value = null
    // 就地同步当前会话，不整页 reload，避免覆盖懒加载列表与滚动位置
    const cur = sessions.value.find((x) => x.id === sid)
    if (cur) {
      cur.title = cur.title || text
      cur.updatedAt = new Date().toISOString()
      cur.msgCount = (cur.msgCount ?? 0) + 1
    } else if (sessionsData.value) {
      const fresh = sessionsData.value.items.find((x) => x.id === sid)
      if (fresh) sessions.value.unshift(fresh)
    }
  }
}

function stop() {
  askAbort.value?.abort()
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

/* ---------- 附件（多模态：图片 / 音频 / 视频） ---------- */
async function onAttach(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  for (const f of files) {
    const kind = kindOf(f)
    if (!kind) continue
    try {
      // 优先 OSS 直传拿可访问地址；未启用则回退本地 base64
      try {
        const { url } = await uploadToOss(f, 'uploads/chat')
        attached.value.push({ kind, mimeType: f.type, url, name: f.name })
      } catch (ossErr: any) {
        if (String(ossErr?.message || '').includes('OSS 未启用')) {
          const b64 = await readFileB64(f)
          attached.value.push({ kind, mimeType: f.type, dataB64: b64, name: f.name })
        } else {
          throw ossErr
        }
      }
    } catch {
      toast.error(`读取/上传文件失败：${f.name}`)
    }
  }
  input.value = ''
}

function removeAttach(i: number) {
  attached.value.splice(i, 1)
}

/* ---------- 反馈 ---------- */
async function onFeedback(m: ChatMessage, rating: 'up' | 'down') {
  if (!m.messageId) return
  const next = m.feedback === rating ? null : rating
  try {
    if (next) await submitFeedback(m.messageId, next)
    else await deleteFeedback(m.messageId)
    m.feedback = next
  } catch (e: any) {
    toast.error(`反馈失败：${e?.message || e}`)
  }
}

/* ---------- 建议 ---------- */
function pick(s: string) {
  inputText.value = s
}

onMounted(() => {
  void loadSessions()
})
watch(messages, scrollToBottom, { deep: false })
</script>

<template>
  <div class="chat-page">
    <!-- ====== 左栏：会话列表 ====== -->
    <aside class="chat-sidebar">
      <div class="sidebar-head">
        <div class="sidebar-title">
          <span>对话</span>
          <span class="sidebar-count">{{ sessionTotal }}</span>
        </div>
      </div>

      <div class="conv-list" ref="convListRef" @scroll="onConvScroll">
        <button
          v-for="s in sessions"
          :key="s.id"
          class="conv-item"
          :class="{ active: s.id === activeId }"
          @click="selectSession(s.id)"
        >
          <span class="conv-dot" />
          <span class="conv-body">
            <span class="conv-q">{{ s.title || '（新会话）' }}</span>
            <span class="conv-meta">
              <span class="conv-time">{{ s.updatedAt ? s.updatedAt.slice(5, 10) : '' }}</span>
              <span class="conv-sep">·</span>
              <span>{{ s.msgCount }} 条</span>
            </span>
          </span>
          <span class="conv-del" title="删除会话" @click.stop="onDeleteSession(s.id)">
            <Icon name="trash" :size="14" />
          </span>
        </button>
        <p v-if="!sessions.length && !sessionLoadingMore" class="conv-empty">还没有对话，点击右上角开始。</p>
        <div v-if="sessionLoadingMore" class="conv-loading-more">
          <span class="dot-sm" /><span class="dot-sm" /><span class="dot-sm" />
        </div>
        <p v-if="allSessionsLoaded && sessions.length > 0" class="conv-all-done">已全部加载</p>
      </div>
    </aside>

    <!-- ====== 中栏：对话区 ====== -->
    <main class="chat-main">
      <div class="card chat-panel">
      <!-- 头部 -->
      <header class="chat-header">
        <div class="chat-head-left">
          <div class="chat-eyebrow">智能问答</div>
          <h1 class="chat-question">{{ firstQuestion || '有什么可以帮你？' }}</h1>
        </div>
        <div class="chat-head-actions">
          <button class="btn btn-primary btn-sm" @click="newChat">
            <Icon name="plus" :size="14" />
            <span>新建对话</span>
          </button>
          <button class="ghost-btn chat-clear" @click="showClearConfirm = true">
            <Icon name="trash" :size="14" />
            <span>清空对话</span>
          </button>
        </div>
      </header>

      <!-- 消息区 + 输入区（共用灰色背景） -->
      <div class="chat-body">
      <!-- 消息区 -->
      <div class="messages-area" ref="scrollRef">
        <!-- 空状态（hero） -->
        <div v-if="!messages.length" class="empty-hero">
          <div class="empty-orb">
            <Icon name="sparkles" :size="28" />
          </div>
          <h2 class="empty-title">向企业知识库提问</h2>
          <p class="empty-sub">基于内部文档检索作答，可附图片进行多模态提问。回答均标注引用来源。</p>
          <div class="empty-suggest">
            <button v-for="(s, i) in suggested" :key="i" class="empty-card" @click="pick(s)">
              <Icon name="arrow-up-right" :size="15" class="empty-card-icon" />
              <span>{{ s }}</span>
            </button>
          </div>
        </div>

        <article
          v-for="m in messages"
          :key="m.id"
          class="msg-row"
          :class="m.role === 'user' ? 'user-msg' : 'ai-msg'"
        >
          <!-- AI 头像 -->
          <div v-if="m.role !== 'user'" class="msg-avatar">
            <Icon name="sparkles" :size="15" />
          </div>

          <div class="msg-bubble">
            <!-- 用户附件 -->
            <div class="attach-thumbs" v-if="m.role === 'user' && m.attachments?.length">
              <template v-for="(a, i) in m.attachments" :key="i">
                <img v-if="a.kind === 'image'" :src="attachSrc(a)" class="attach-thumb" />
                <audio v-else-if="a.kind === 'audio'" :src="attachSrc(a)" controls class="attach-media" />
                <video v-else-if="a.kind === 'video'" :src="attachSrc(a)" controls class="attach-media" />
                <span v-else class="attach-badge">{{ a.kind }}</span>
              </template>
            </div>

            <!-- 思考过程 -->
            <div v-if="m.role !== 'user' && m.thinkingSteps?.length" class="thinking">
              <button class="thinking-toggle" @click="toggleThinking(m.id)">
                <Icon name="sparkles" :size="14" />
                <span>思考过程</span>
                <span class="thinking-count">{{ m.thinkingSteps.length }}</span>
                <Icon name="chevron-down" :size="13" class="thinking-chev" :class="{ open: expandedThinking.has(m.id) }" />
              </button>
              <ol v-if="expandedThinking.has(m.id)" class="thinking-list">
                <li v-for="t in m.thinkingSteps" :key="t.step">
                  <span class="think-step">{{ t.step }}</span>
                  <span class="think-action">{{ t.action }}</span>
                  <span class="think-detail">{{ t.detail }}</span>
                </li>
              </ol>
            </div>

            <!-- 正文 -->
            <div v-if="m.content" class="answer-body">{{ m.content }}</div>
            <div v-else-if="streaming" class="answer-loading">
              <span class="dot" /><span class="dot" /><span class="dot" />
            </div>

            <!-- 引用文档 -->
            <div v-if="m.role !== 'user' && m.sources?.length" class="refs">
              <div class="refs-label">
                <Icon name="quote" :size="14" />
                <span>引用来源（{{ m.sources.length }}）</span>
              </div>
              <div class="refs-grid">
                <div v-for="(s, i) in m.sources" :key="s.id ?? i" class="ref-card" :class="{ 'ref-clickable': s.sourceType === 'kb' }" @click="openDocDetail(s)" :title="s.sourceType === 'kb' ? '点击查看文档详情' : undefined">
                  <span class="ref-icon" :class="`src-${s.sourceType || 'kb'}`">
                    <Icon :name="s.sourceType === 'web' ? 'globe' : s.sourceType === 'graph' ? 'graph' : 'doc'" :size="16" />
                  </span>
                  <div class="ref-info">
                    <div class="ref-name">{{ s.title }}</div>
                    <div class="ref-meta">
                      <span class="ref-kb">{{ s.kb || '知识库' }}</span>
                      <span class="ref-conf">{{ s.confidence ? Math.round(s.confidence * 100) + '% 相关' : '相关' }}</span>
                    </div>
                    <p v-if="s.snippet" class="ref-snippet">{{ s.snippet }}</p>
                  </div>
                </div>
              </div>
            </div>

            <!-- 错误 -->
            <div v-if="m.role !== 'user' && errorMsg && !m.content" class="answer-error">
              <Icon name="alert" :size="14" />
              <span>{{ errorMsg }}</span>
            </div>

            <!-- 反馈 + 操作 -->
            <div v-if="m.role !== 'user' && m.messageId && m.content" class="msg-actions">
              <span class="msg-actions-divider" />
              <button class="act-btn" title="复制回答" @click="copyAnswer(m)">
                <Icon name="copy" :size="14" />
              </button>
              <button
                v-if="auth.user?.ttsEnabled"
                class="act-btn"
                :class="{ on: playingId === m.id }"
                :title="playingId === m.id ? '播报中…' : '朗读回答'"
                @click="speak(m)"
              >
                <Icon :name="playingId === m.id ? 'loader' : 'volume'" :size="14" :class="{ spin: playingId === m.id }" />
              </button>
              <button class="act-btn" :class="{ on: m.feedback === 'up' }" title="有用" @click="onFeedback(m, 'up')">
                <Icon name="thumbs-up" :size="14" />
              </button>
              <button class="act-btn" :class="{ on: m.feedback === 'down' }" title="没用" @click="onFeedback(m, 'down')">
                <Icon name="thumbs-down" :size="14" />
              </button>
            </div>
          </div>
        </article>
      </div>

      <!-- 建议追问 -->
      <div class="suggest-row" v-if="!streaming && messages.length">
        <span class="suggest-label">你可能还想问</span>
        <button v-for="(s, i) in suggested" :key="i" class="chip" @click="pick(s)">{{ s }}</button>
      </div>

      <!-- 输入区（仅对话视图显示） -->
      <div class="composer">
        <div v-if="attached.length" class="attach-preview">
          <div v-for="(a, i) in attached" :key="i" class="attach-chip">
            <img v-if="a.kind === 'image'" :src="attachSrc(a)" class="attach-thumb" />
            <audio v-else-if="a.kind === 'audio'" :src="attachSrc(a)" controls class="attach-media" />
            <video v-else-if="a.kind === 'video'" :src="attachSrc(a)" controls class="attach-media" />
            <span v-else class="attach-badge">{{ a.kind }}</span>
            <button class="attach-x" @click="removeAttach(i)"><Icon name="close" :size="11" /></button>
          </div>
        </div>

        <textarea
          v-model="inputText"
          class="composer-input"
          rows="4"
          placeholder="输入问题，Shift + Enter 换行，Enter 发送"
          @keydown="onKeydown"
        ></textarea>

        <div class="composer-bar">
          <div class="composer-left">
            <label class="composer-attach" title="附图片 / 音频 / 视频">
              <Icon name="attach" :size="17" />
              <input type="file" accept="image/*,audio/*,video/*" multiple class="file-hidden" @change="onAttach" />
            </label>
            <span class="composer-count">{{ inputText.length }} / 2000</span>
          </div>
          <div class="composer-right">
            <button v-if="streaming" class="stop-btn" @click="stop">
              <Icon name="square" :size="13" />
              <span>停止</span>
            </button>
            <button v-else class="send-btn" :disabled="!inputText.trim()" @click="send">
              <span>发送</span>
              <Icon name="arrow-up" :size="15" />
            </button>
          </div>
        </div>
      </div>
      </div>
    </div>
    </main>
  </div>


  <ConfirmDialog
    :show="!!deleteTargetId"
    title="删除会话"
    message="确认删除该会话？删除后无法恢复。"
    confirm-text="删除"
    danger
    @close="deleteTargetId = null"
    @confirm="confirmDeleteSession"
  />

  <ConfirmDialog
    :show="showClearConfirm"
    title="清空对话"
    message="确认清空当前对话的所有消息？此操作不可撤销。"
    confirm-text="清空"
    danger
    @close="showClearConfirm = false"
    @confirm="confirmClear"
  />

  <!-- 文档详情弹框 -->
  <AppModal
    :show="!!docDetail"
    :title="docDetail?.title || '文档详情'"
    wide
    @close="docDetail = null"
  >
    <template v-if="docDetailLoading" #default>
      <div class="doc-detail-loading">
        <span class="dot" /><span class="dot" /><span class="dot" />
      </div>
    </template>
    <template v-else-if="docDetail" #default>
      <div class="doc-detail">
        <div class="doc-meta-grid">
          <div class="doc-meta-item">
            <span class="doc-meta-label">类型</span>
            <span class="doc-meta-value">{{ detail.type || '—' }}</span>
          </div>
          <div class="doc-meta-item">
            <span class="doc-meta-label">状态</span>
            <span class="doc-meta-value" :class="'status-' + (detail.status || '')">{{ detail.status || '—' }}</span>
          </div>
          <div class="doc-meta-item">
            <span class="doc-meta-label">更新时间</span>
            <span class="doc-meta-value mono">{{ detail.updatedAt?.slice(0, 16) || '—' }}</span>
          </div>
        </div>
        <div v-if="detail.originalFilename" class="doc-file-info">
          <Icon name="file-text" :size="14" />
          <span>{{ detail.originalFilename }}</span>
          <span v-if="detail.fileSize" class="doc-file-size">({{ formatSize(detail.fileSize) }})</span>
        </div>
        <div v-if="detail.reviewedAt" class="doc-review-info">
          审核于 {{ detail.reviewedAt.slice(0, 16) }}
          <span v-if="detail.reviewedBy"> · {{ detail.reviewedBy }}</span>
        </div>
        <div class="doc-content">
          <div class="doc-content-label">文档内容</div>
          <pre class="doc-content-body">{{ detail.contentMd }}</pre>
        </div>
      </div>
    </template>
  </AppModal>
</template>

<style scoped>
.chat-page {
  display: flex;
  height: calc(100vh - var(--topbar-h) - 48px);
  min-height: 520px;
  background: var(--bg-page);
}
.chat-page :deep(.file-hidden) {
  position: absolute;
  inset: 0;
  opacity: 0;
  width: 100%;
  cursor: pointer;
}


/* ============ 侧栏 ============ */
.chat-sidebar {
  width: 272px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg-surface);
}
.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 18px 14px;
}
.sidebar-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}
.sidebar-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
  background: var(--bg-subtle);
  padding: 1px 8px;
  border-radius: var(--radius-pill);
}
.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.conv-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 11px 12px;
  border-radius: var(--radius-md);
  text-align: left;
  color: var(--text-secondary);
  transition: background var(--dur-fast) var(--ease-out);
}
.conv-item:hover { background: var(--bg-hover); }
.conv-item.active {
  background: var(--brand-soft);
  color: var(--text-primary);
}
.conv-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-tertiary);
  flex-shrink: 0;
  transition: background var(--dur-fast);
}
.conv-item.active .conv-dot { background: var(--brand); }
.conv-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.conv-q {
  font-size: 13px;
  font-weight: 600;
  color: inherit;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-item.active .conv-q { color: var(--brand); }
.conv-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-tertiary);
}
.conv-sep { opacity: 0.6; }
.conv-del {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  opacity: 0;
  transition: all var(--dur-fast) var(--ease-out);
}
.conv-item:hover .conv-del { opacity: 1; }
.conv-del:hover { background: var(--danger-soft); color: var(--danger); }
.conv-empty {
  margin: 24px 8px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-tertiary);
  text-align: center;
}
.conv-loading-more {
  display: flex;
  justify-content: center;
  gap: 4px;
  padding: 12px 0 6px;
}
.dot-sm {
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--text-tertiary);
  animation: blink 1.3s infinite ease-in-out;
}
.conv-loading-more .dot-sm:nth-child(2) { animation-delay: 0.18s; }
.conv-loading-more .dot-sm:nth-child(3) { animation-delay: 0.36s; }
.conv-all-done {
  text-align: center;
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
}

/* ============ 对话主区 ============ */
.chat-main {
  margin-left: 10px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.chat-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  padding: 20px;
}
.chat-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: var(--bg-subtle);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 18px;
  margin-bottom: 4px;
}
.chat-head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.chat-eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand);
  margin-bottom: 4px;
}
.chat-question {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.02em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60vw;
}
.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  font-size: 12.5px;
  color: var(--text-secondary);
  transition: all var(--dur-fast) var(--ease-out);
}
.ghost-btn:hover { background: var(--bg-hover); color: var(--text-primary); border-color: var(--border-strong); }

/* ============ 消息区 ============ */
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 15px 10px 15px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 空状态 hero */
.empty-hero {
  margin: auto;
  text-align: center;
  max-width: 500px;
  display: flex;
  flex-direction: column;
  align-items: center;
  animation: fade-up 0.4s var(--ease-out) both;
}
.empty-orb {
  width: 68px;
  height: 68px;
  border-radius: 24px;
  background: linear-gradient(135deg, var(--brand) 0%, var(--brand-hover) 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 22px;
  box-shadow: 0 12px 32px var(--brand-ring);
}
.empty-title { font-size: 20px; font-weight: 700; color: var(--text-primary); margin: 0 0 10px; letter-spacing: -0.02em; }
.empty-sub { font-size: 14px; line-height: 1.7; color: var(--text-secondary); margin: 0 0 28px; }
.empty-suggest {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  width: 100%;
}
.empty-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  text-align: left;
  transition: all var(--dur-fast) var(--ease-out);
}
.empty-card:hover {
  border-color: var(--brand);
  background: var(--brand-soft);
  transform: translateY(-2px);
  box-shadow: var(--shadow-float);
}
.empty-card-icon { color: var(--brand); flex-shrink: 0; }

/* 消息气泡 */
.msg-row {
  display: flex;
  gap: 12px;
  max-width: 840px;
  width: 100%;
  animation: fade-up 0.32s var(--ease-out) both;
}
.msg-row.user-msg { align-self: flex-end; max-width: 680px; flex-direction: row-reverse; }
.msg-row.ai-msg { align-items: flex-start; }
.msg-avatar {
  width: 34px;
  height: 34px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
  background: linear-gradient(135deg, var(--brand) 0%, var(--brand-hover) 100%);
  margin-top: 2px;
}
.msg-bubble {
  min-width: 0;
  padding: 14px 18px;
  border-radius: var(--radius-lg);
  font-size: 13.5px;
  line-height: 1.78;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-row.ai-msg .msg-bubble {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 6px var(--radius-lg) var(--radius-lg) var(--radius-lg);
  box-shadow: var(--shadow-card);
  flex: 1;
}
.msg-row.user-msg .msg-bubble {
  background: var(--brand);
  color: var(--text-on-brand);
  border-radius: var(--radius-lg) 6px var(--radius-lg) var(--radius-lg);
}

/* 思考过程 */
.thinking {
  margin-bottom: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-subtle);
  overflow: hidden;
}
.thinking-toggle {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  padding: 9px 13px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}
.thinking-toggle:hover { color: var(--text-primary); }
.thinking-count {
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 11px;
  font-weight: 700;
  padding: 0 7px;
  border-radius: var(--radius-pill);
}
.thinking-chev { margin-left: auto; color: var(--text-tertiary); transition: transform var(--dur-fast) var(--ease-out); }
.thinking-chev.open { transform: rotate(180deg); }
.thinking-list { margin: 0; padding: 4px 14px 12px; list-style: none; display: flex; flex-direction: column; gap: 7px; }
.thinking-list li { display: flex; align-items: baseline; gap: 8px; font-size: 12px; color: var(--text-tertiary); line-height: 1.55; }
.think-step {
  flex-shrink: 0;
  width: 18px; height: 18px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 11px;
  font-weight: 700;
}
.think-action {
  flex-shrink: 0;
  font-weight: 600;
  color: var(--text-secondary);
}

/* 加载圆点 */
.answer-loading { display: flex; gap: 5px; padding: 6px 0; }
.answer-loading .dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--text-tertiary);
  animation: blink 1.3s infinite ease-in-out;
}
.answer-loading .dot:nth-child(2) { animation-delay: 0.18s; }
.answer-loading .dot:nth-child(3) { animation-delay: 0.36s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.25; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-3px); } }

.answer-error {
  display: flex; align-items: center; gap: 6px;
  margin-top: 12px; font-size: 12.5px; color: var(--danger);
}

/* 引用来源 */
.refs { margin-top: 16px; }
.refs-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 12.5px; font-weight: 600; color: var(--text-secondary);
  margin-bottom: 10px;
}
.refs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.ref-card {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 11px 13px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface-2);
  transition: all var(--dur-fast) var(--ease-out);
}
.ref-card:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-float);
  transform: translateY(-2px);
}
.ref-icon {
  width: 34px; height: 34px;
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.ref-icon.src-kb { background: var(--info-soft); color: var(--info); }
.ref-icon.src-web { background: var(--success-soft); color: var(--success); }
.ref-icon.src-graph { background: var(--warning-soft); color: var(--warning); }
.ref-info { min-width: 0; flex: 1; }
.ref-name {
  font-size: 12.5px; font-weight: 600; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ref-meta { display: flex; gap: 8px; font-size: 11px; color: var(--text-tertiary); margin: 3px 0 4px; }
.ref-kb { color: var(--brand); font-weight: 600; }
.ref-snippet {
  margin: 0;
  font-size: 11.5px;
  color: var(--text-tertiary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 操作行 */
.msg-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 14px;
}
.msg-actions-divider {
  flex: 1;
  height: 1px;
  background: var(--border);
  margin-right: 8px;
}
.act-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  transition: all var(--dur-fast) var(--ease-out);
}
.act-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.act-btn.on { background: var(--brand-soft); color: var(--brand); }

/* ============ 建议追问 ============ */
.suggest-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 15px 8px;
  flex-wrap: wrap;
}
.suggest-label { font-size: 12.5px; font-weight: 600; color: var(--text-tertiary); white-space: nowrap; }
.chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-surface);
  font-family: inherit;
  transition: all var(--dur-fast) var(--ease-out);
  white-space: nowrap;
}
.chip:hover { border-color: var(--brand); color: var(--brand); background: var(--brand-soft); }

/* ============ 输入区（composer） ============ */
.composer {
  margin: 5px 10px 10px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
  box-shadow: var(--shadow-card);
  transition: border-color var(--dur-fast), box-shadow var(--dur-fast);
}
.composer:focus-within {
  border-color: var(--brand);
  box-shadow: 0 0 0 4px var(--brand-ring);
}
.attach-preview { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.attach-chip { position: relative; }
.attach-thumb { width: 50px; height: 50px; border-radius: 9px; object-fit: cover; border: 1px solid var(--border); }
.attach-media { width: 200px; max-width: 60vw; border-radius: 9px; border: 1px solid var(--border); }
.attach-badge { display: inline-flex; padding: 4px 10px; border-radius: 9px; background: var(--bg-subtle); color: var(--text-secondary); font-size: 12px; }
.attach-x {
  position: absolute;
  top: -6px; right: -6px;
  width: 19px; height: 19px;
  border-radius: 50%;
  background: var(--danger);
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  transition: background var(--dur-fast);
}
.attach-x:hover { background: var(--danger-hover); }

.composer-input {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  min-height: 90px;
  font-family: inherit;
  max-height: 180px;
  padding: 2px 2px;
}
.composer-input::placeholder { color: var(--text-placeholder); }

.composer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}
.composer-left { display: flex; align-items: center; gap: 12px; }
.composer-attach {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px; height: 36px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  overflow: hidden;
  transition: all var(--dur-fast) var(--ease-out);
}
.composer-attach:hover { background: var(--bg-hover); color: var(--brand); }
.composer-count { font-size: 12px; color: var(--text-tertiary); }
.composer-right { display: flex; align-items: center; gap: 8px; }

.send-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 38px;
  padding: 0 18px;
  border-radius: var(--radius-md);
  background: var(--brand);
  color: var(--text-on-brand);
  font-size: 13px;
  font-weight: 600;
  transition: background var(--dur-fast) var(--ease-out), transform var(--dur-fast);
}
.send-btn:hover:not(:disabled) { background: var(--brand-hover); }
.send-btn:active:not(:disabled) { transform: translateY(1px); }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 38px;
  padding: 0 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  transition: all var(--dur-fast) var(--ease-out);
}
.stop-btn:hover { background: var(--bg-hover); color: var(--text-primary); }

@keyframes fade-up {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin 0.9s linear infinite; }

@media (max-width: 720px) {
  .chat-sidebar { width: 210px; }
  .empty-suggest { grid-template-columns: 1fr; }
  .chat-question { max-width: 50vw; }
}

/* ============ 文档详情弹框 ============ */
.ref-clickable {
  cursor: pointer;
}
.ref-clickable:hover {
  border-color: var(--brand);
  transform: translateY(-2px);
  box-shadow: var(--shadow-float);
}

.doc-detail-loading {
  display: flex;
  gap: 6px;
  padding: 40px 0;
  justify-content: center;
}
.doc-detail-loading .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--text-tertiary);
  animation: blink 1.3s infinite ease-in-out;
}
.doc-detail-loading .dot:nth-child(2) { animation-delay: 0.18s; }
.doc-detail-loading .dot:nth-child(3) { animation-delay: 0.36s; }

.doc-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.doc-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 20px;
}
.doc-meta-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.doc-meta-label {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.doc-meta-value {
  font-size: 13.5px;
  color: var(--text-primary);
  font-weight: 500;
}
.mono { font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', Consolas, monospace); }
.doc-meta-value.status-已审核 { color: var(--success); }
.doc-meta-value.status-待复核 { color: var(--warning); }
.doc-meta-value.status-已拒绝 { color: var(--danger); }

.doc-file-info {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
}
.doc-file-size {
  color: var(--text-tertiary);
  font-size: 12px;
}
.doc-review-info {
  font-size: 12.5px;
  color: var(--text-tertiary);
}

.doc-content {
  border-top: 1px solid var(--border);
  padding-top: 14px;
}
.doc-content-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.doc-content-body {
  margin: 0;
  padding: 14px 16px;
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.75;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

</style>
