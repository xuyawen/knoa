<script setup lang="ts">
// 智能问答 — 对话主界面，接真实 SSE 流式问答。
import { ref, computed, onMounted, onActivated, onDeactivated, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import Icon from '@/components/ui/Icon.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import ChatSessionList from '@/components/chat/ChatSessionList.vue'
import DocDetailModal from '@/components/chat/DocDetailModal.vue'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { useAsyncAction } from '@/composables/useAsyncAction'
import { useAuthStore } from '@/stores/auth'
import {
  getSessions,
  createSession,
  getSession,
  deleteSession,
  clearSessionMessages,
  renameSession,
  pinSession,
  deleteMessage,
  streamAsk,
  submitFeedback,
  deleteFeedback,
  getDocument,
  getKnowledgeBases,
  getTrending,
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
  KnowledgeBase,
} from '@/types/api'
import { uploadToOss } from '@/utils/oss'
import { useModelConfig } from '@/composables/useModelConfig'
import { useTts } from '@/composables/useTts'

// 显式组件名：与 AppLayout 中 KeepAlive include="Chat" 匹配，缓存对话页状态
defineOptions({ name: 'Chat' })

/** 生成唯一 ID（兼容非安全上下文 HTTP 下 crypto.randomUUID 不可用） */
function genId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // Fallback: RFC 4122 v4 UUID（足够用于前端消息 ID）
  return '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, c =>
    ((+c) ^ (crypto?.getRandomValues(new Uint8Array(1))[0] & (15 >> (+c / 4)))).toString(16)
  )
}

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

// 语音播报（P8）：朗读某条 AI 回答（逻辑在 useTts，含卸载清理）
const { playingId, speak } = useTts()

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
const { busy: deletingSession, run: runDeleteSession } = useAsyncAction({ errorPrefix: '删除失败' })
const { run: runPinSession } = useAsyncAction({ errorPrefix: '置顶操作失败' })
const showClearConfirm = ref(false)
const messages = ref<ChatMessage[]>([])
const streaming = ref(false)
const inputText = ref('')
const inputRef = ref<HTMLTextAreaElement>()
// 提问字数上限（与后端 AskRequest.max_length 同步）：超出计数变红、禁用发送
const QUESTION_MAX_LEN = 8000
/** 输入框随内容增高至最多 4 行，超出出现内部滚动条，高度不再变大 */
const INPUT_MAX_PX = 112 // 4 行 × 22.4px + 上下 padding 22px
function autoGrow() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, INPUT_MAX_PX)}px`
}
watch(inputText, () => nextTick(autoGrow))
const errorMsg = ref('')
// V4：问答失败后保留上一问题（含附件），供内联「重试」按钮复发
const retryPayload = ref<{ text: string; attachments: ChatAttachment[] | null } | null>(null)
const askAbort = ref<AbortController | null>(null)
const attached = ref<ChatAttachment[]>([])
const deepThinking = ref(false)      // ping 事件驱动：LLM 长调用中显示「深度思考」提示
const followUps = ref<string[]>([])  // follow_ups 事件：答后生成的相关追问
const expandedThinking = ref<Set<string>>(new Set())
function toggleThinking(id: string) {
  const next = new Set(expandedThinking.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedThinking.value = next
}

// 组件卸载时中断进行中的问答流（TTS 清理在 useTts 内）
onBeforeUnmount(() => {
  askAbort.value?.abort()
  document.removeEventListener('mousedown', onHeadOutside)
  window.removeEventListener('keydown', onHeadEsc)
})
// keep-alive 隐藏页面时摘除全局监听，避免后台页面仍响应点击/Esc
onDeactivated(() => {
  document.removeEventListener('mousedown', onHeadOutside)
  window.removeEventListener('keydown', onHeadEsc)
})

// 文档详情弹框（展示逻辑在 DocDetailModal）
const docDetail = ref<DocumentDetail | null>(null)
const docDetailLoading = ref(false)
// 引用片段：传给 DocDetailModal 在全文中高亮定位
const docDetailSnippet = ref('')
async function openDocDetail(s: SourceItem) {
  // 联网来源：有链接则新窗口打开
  if (s.sourceType === 'web' && s.url) {
    window.open(s.url, '_blank', 'noopener,noreferrer')
    return
  }
  // 知识库 / 图谱来源：必须有 kbId + docId 才能查文档详情
  if (!s.kbId || !s.docId) {
    toast.warning('该引用缺少文档标识，无法查看详情')
    return
  }
  docDetailSnippet.value = s.snippet ?? ''
  docDetailLoading.value = true
  docDetail.value = null
  try {
    docDetail.value = await getDocument(s.kbId, s.docId)
  } catch (e: unknown) {
    toast.error(`加载文档失败：${errMsg(e)}`)
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

/* 推荐问题：动态取热搜榜（后端已按用户可见部门过滤），无数据时回落通用示例。 */
const FALLBACK_SUGGESTED = [
  '知识库中有哪些内容？',
  '帮我总结某份文档的核心要点',
  '这个问题应该问哪个部门？',
  '最近新增了哪些文档？',
]
const suggested = ref<string[]>([])
async function loadSuggested() {
  try {
    const items = await getTrending()
    if (items.length >= 4) {
      suggested.value = items.slice(0, 4).map((t) => t.question)
    } else if (items.length > 0) {
      // 热搜不足 4 条，用 fallback 补全（去重）
      const hot = items.map((t) => t.question)
      const extra = FALLBACK_SUGGESTED.filter((s) => !hot.includes(s))
      suggested.value = [...hot, ...extra].slice(0, 4)
    } else {
      suggested.value = FALLBACK_SUGGESTED
    }
  } catch {
    suggested.value = FALLBACK_SUGGESTED
  }
}

// 检索范围：默认搜全部可访问知识库；选定具体 KB 后仅在该库内检索，
// 后端会优先走 ES 快路（kNN + BM25），相关性与速度都更好
const kbOptions = ref<KnowledgeBase[]>([])
// CustomSelect 选项：首项「全部知识库」（value='' 表示不限定范围）+ 各可见库
const kbSelectOptions = computed(() => [
  { label: '全部知识库', value: '' },
  ...kbOptions.value.map((kb) => ({ label: kb.name, value: kb.id })),
])
// 记住上次选择的知识库（跨页面跳转保持）
const KB_STORAGE_KEY = 'knoa.chat.selectedKb'
const selectedKb = ref(localStorage.getItem(KB_STORAGE_KEY) || '')
watch(selectedKb, (v) => localStorage.setItem(KB_STORAGE_KEY, v))
async function loadKbOptions() {
  try {
    const res = await getKnowledgeBases(1, 100)
    kbOptions.value = res.knowledgeBases
    // 之前选中的 KB 已不可访问（被删/权限收回）→ 重置为全库
    if (selectedKb.value && !kbOptions.value.some((k) => k.id === selectedKb.value)) {
      selectedKb.value = ''
    }
  } catch {
    // 知识库列表加载失败不阻断问答（回退全库检索）
  }
}

/* ---------- 工具 ---------- */
// V3：用户上滑查看历史时暂停自动滚底，回到底部附近后恢复；
// force=true（发送/切会话）无条件滚底并重置标志。
const autoScroll = ref(true)

function onMsgScroll(e: Event) {
  const el = e.target as HTMLElement
  if (!el) return
  autoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 80
}

function scrollToBottom(force = false) {
  if (force) autoScroll.value = true
  if (!autoScroll.value) return
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

/** 多模态附件 → 展示地址：OSS 直传 url 优先；无 url 时回退 base64 内联（旧流程/历史回显）。 */
function attachSrc(a: { url?: string; mimeType?: string; dataB64?: string }): string {
  return a.url || `data:${a.mimeType};base64,${a.dataB64}`
}

/** 对话附件支持的文档扩展名（提取文本注入上下文，全模型可用）。 */
const DOC_EXTS = ['md', 'txt', 'docx', 'pdf']

/** 由 MIME/扩展名推断附件种类：图片（需视觉模型）或文档（全模型）。音视频已移除。 */
function kindOf(file: File): 'image' | 'document' | null {
  if (file.type.startsWith('image/')) return 'image'
  const ext = file.name.includes('.') ? file.name.split('.').pop()!.toLowerCase() : ''
  if (DOC_EXTS.includes(ext)) return 'document'
  return null
}

// accept 恒含 image/*：文件选择框在打开瞬间读取 accept，若此时 /api/settings
// 尚未返回（chatVision 还是默认 false），图片会被系统对话框直接过滤掉；
// 是否允许图片改由 onAttach 按 chatVision 真值判断（未配置时 toast 拦截）
const chatVision = computed(() => state.chatVision)
const acceptAttr = 'image/*,.md,.txt,.docx,.pdf'

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

/* ---------- Markdown 渲染 + 引用角标 ---------- */
// LLM 回答含列表/加粗/代码块，用 marked 渲染、DOMPurify 防注入；
// [N] 引用角标转为可点击 chip，点击高亮对应来源卡片。
marked.use({ breaks: true, gfm: true })
function renderAnswer(content: string): string {
  if (!content) return ''
  const html = marked.parse(content, { async: false }) as string
  const withCites = html.replace(
    /\[(\d{1,3})\]/g,
    '<button type="button" class="cite-chip" data-cite="$1">$1</button>',
  )
  return DOMPurify.sanitize(withCites)
}

/** 角标点击：滚动到同一条回答内编号相同的来源卡并闪烁高亮。 */
function onCiteClick(e: Event) {
  const chip = (e.target as HTMLElement).closest('.cite-chip')
  if (!chip) return
  const n = chip.getAttribute('data-cite')
  const row = chip.closest('.msg-row')
  const card = n && row ? (row.querySelector(`.ref-card[data-ref-id="${n}"]`) as HTMLElement | null) : null
  if (!card) return
  card.scrollIntoView({ behavior: 'smooth', block: 'center' })
  card.classList.remove('ref-flash')
  void card.offsetWidth // 强制重排，让高亮动画可重复触发
  card.classList.add('ref-flash')
}

function toChatMessage(m: SessionMessage): ChatMessage {
  return {
    id: genId(),
    role: m.role === 'assistant' ? 'assistant' : 'user',
    content: m.content,
    citations: m.citations ?? undefined,
    sources: m.sources || undefined,
    attachments: m.attachments || null,
    thinkingSteps: m.thinkingSteps || undefined,
    feedback: null,
    messageId: m.id || undefined,
  }
}

/* ---------- 会话（懒加载；列表 UI 在 ChatSessionList） ---------- */
async function loadSessions(append = false) {
  if (sessionLoadingMore.value) return
  // "已全部加载"仅阻止追加翻页，不阻止刷新（删除/新建后需重新拉取）
  if (append && allSessionsLoaded.value) return
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
  } catch (e: unknown) {
    toast.error(`加载会话失败：${errMsg(e)}`)
  } finally {
    sessionLoadingMore.value = false
  }
}

async function selectSession(id: string) {
  askAbort.value?.abort()
  streaming.value = false
  activeId.value = id
  // 附件属于原会话的草稿，切换时清空，避免误发到别的会话
  attached.value = []
  errorMsg.value = ''
  followUps.value = []
  try {
    const det = await getSession(id)
    messages.value = det.messages.map(toChatMessage)
    scrollToBottom(true)
  } catch (e: unknown) {
    toast.error(`加载会话失败：${errMsg(e)}`)
  }
}

async function newChat() {
  askAbort.value?.abort()
  streaming.value = false
  // 延迟创建：不立即调后端 createSession，等用户发第一条消息时再建。
  // 避免点了「新建对话」却没提问，产生 0 条的空会话记录。
  activeId.value = null
  messages.value = []
  inputText.value = ''
  attached.value = []
  errorMsg.value = ''
  followUps.value = []
}

// ---------- 侧边栏收起（localStorage 持久化） ----------
const sidebarCollapsed = ref(localStorage.getItem('knoa.chatSidebar') === 'collapsed')
function setSidebarCollapsed(v: boolean) {
  sidebarCollapsed.value = v
  localStorage.setItem('knoa.chatSidebar', v ? 'collapsed' : 'open')
}

/** 置顶切换：调 API 后重拉列表，保证置顶组排最前的排序生效 */
async function onPinSession(id: string) {
  await runPinSession(async () => {
    await pinSession(id)
    await loadSessions()
  })
}

// ---------- 头部 ⋯ 菜单（低频操作：导出 / 清空对话） ----------
const headMenuOpen = ref(false)
const headMenuPos = ref({ top: 0, left: 0 })

function openHeadMenu(e: MouseEvent) {
  if (headMenuOpen.value) {
    headMenuOpen.value = false
    return
  }
  const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
  headMenuPos.value = { top: r.bottom + 6, left: Math.max(8, r.right - 160) }
  headMenuOpen.value = true
}
function headExport() {
  headMenuOpen.value = false
  exportSession()
}
function headClear() {
  headMenuOpen.value = false
  showClearConfirm.value = true
}
function onHeadOutside(e: MouseEvent) {
  if (!headMenuOpen.value) return
  const t = e.target as HTMLElement
  if (t.closest('.head-menu') || t.closest('.head-more')) return
  headMenuOpen.value = false
}
function onHeadEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') headMenuOpen.value = false
}

/** 新会话插入非置顶组最前（置顶会话恒排列表最前） */
function insertSession(s: ChatSession) {
  const idx = sessions.value.findIndex((x) => !x.pinned)
  if (idx === -1) sessions.value.push(s)
  else sessions.value.splice(idx, 0, s)
}

function onDeleteSession(id: string) {
  deleteTargetId.value = id
}

async function confirmDeleteSession() {
  const id = deleteTargetId.value
  if (!id) return
  await runDeleteSession(async () => {
    await deleteSession(id)
    if (activeId.value === id) {
      activeId.value = null
      messages.value = []
      attached.value = []
    }
    await loadSessions()
    toast.success('会话已删除')
  })
  deleteTargetId.value = null
}

/* ---------- 清空对话 ---------- */
async function confirmClear() {
  showClearConfirm.value = false
  const sid = activeId.value
  if (!sid) {
    messages.value = []
    inputText.value = ''
    return
  }
  try {
    // 真清空：后端删消息 + 重置滚动摘要，保证 LLM 上下文一并清空
    // （此前只清前端数组，后端历史还在，模型仍会记得旧内容）
    askAbort.value?.abort()
    streaming.value = false
    await clearSessionMessages(sid)
    messages.value = []
    inputText.value = ''
    followUps.value = []
    toast.success('对话已清空')
  } catch (e: unknown) {
    toast.error(`清空失败：${errMsg(e)}`)
  }
}

/* ---------- 发送（SSE） ---------- */
async function send() {
  const text = inputText.value.trim()
  if (!text || streaming.value) return
  if (inputText.value.length > QUESTION_MAX_LEN) {
    toast.warning(`问题不能超过 ${QUESTION_MAX_LEN} 字`)
    return
  }

  let sid = activeId.value
  if (!sid) {
    try {
      const s = await createSession()
      sid = s.id
      const cur = sessionsData.value
      sessionsData.value = cur
        ? { ...cur, items: [s, ...cur.items], total: cur.total + 1 }
        : { items: [s], total: 1, page: 1, pageSize: 20, pages: 1 }
      insertSession(s)
      activeId.value = sid
    } catch (e: unknown) {
      toast.error(`创建会话失败：${errMsg(e)}`)
      return
    }
  }

  const userMsg: ChatMessage = {
    id: genId(),
    role: 'user',
    content: text,
    attachments: attached.value.length ? [...attached.value] : null,
    feedback: null,
  }
  const aiMsg: ChatMessage = {
    id: genId(),
    role: 'assistant',
    content: '',
    thinkingSteps: [],
    feedback: null,
  }
  messages.value.push(userMsg, aiMsg)
  // 取回 reactive proxy 引用（直接修改 raw 对象不触发 Vue 重渲染）
  const reactiveAiMsg = messages.value[messages.value.length - 1]
  inputText.value = ''
  attached.value = []
  scrollToBottom(true)

  await runStream(text, sid, userMsg.attachments ?? null, reactiveAiMsg)
}

/** SSE 流式核心：发送 / 重新生成共用。 */
async function runStream(
  text: string,
  sid: string,
  attachments: ChatAttachment[] | null,
  aiMsg: ChatMessage,
) {
  streaming.value = true
  errorMsg.value = ''
  retryPayload.value = null
  followUps.value = []
  deepThinking.value = false
  const ac = new AbortController()
  askAbort.value = ac

  // ── 打字机缓冲：后端 delta 可能一次来一大段，逐字释放让视觉更平滑 ──
  let typeBuf = ''
  let typeTimer: ReturnType<typeof setInterval> | null = null
  let streamEnded = false
  const startTypewriter = () => {
    if (typeTimer) return
    typeTimer = setInterval(() => {
      if (!typeBuf) {
        if (streamEnded) {
          // 缓冲排空 + 流已结束 → 真正完成
          clearInterval(typeTimer!); typeTimer = null
          streaming.value = false
        }
        return
      }
      // 每次释放 2 个字符，节奏 ~30ms/字（~60 字/秒）
      const chunk = typeBuf.slice(0, 2)
      typeBuf = typeBuf.slice(2)
      aiMsg.content += chunk
      scrollToBottom()
    }, 30)
  }
  /** 强制冲刷（用于 abort / error 时立即显示全部内容） */
  const flushTypewriter = () => {
    if (typeTimer) { clearInterval(typeTimer); typeTimer = null }
    if (typeBuf) { aiMsg.content += typeBuf; typeBuf = ''; scrollToBottom() }
    streaming.value = false
  }

  try {
    for await (const ev of streamAsk(text, selectedKb.value || null, sid, attachments || undefined, {
      signal: ac.signal,
      modelConfig: readModelConfig(),
    })) {
      if (ev.event === 'thinking') {
        aiMsg.thinkingSteps = [...(aiMsg.thinkingSteps || []), ev.data as ThinkingStep]
      } else if (ev.event === 'sources') {
        aiMsg.sources = ev.data as SourceItem[]
      } else if (ev.event === 'ping') {
        // 后端每次 LLM 调用前推的心跳 → 提示「深度思考」，缓解长等待焦虑
        deepThinking.value = true
      } else if (ev.event === 'delta') {
        deepThinking.value = false
        typeBuf += (ev.data as { content: string }).content
        startTypewriter()
      } else if (ev.event === 'done') {
        const d = ev.data as { messageId: string; sessionId: string; citations?: number[] }
        aiMsg.messageId = d.messageId
        // 模型实际引用的 [n] 编号：done 后用于收窄引用来源展示（流式期间先展示全量召回）
        aiMsg.citations = d.citations ?? []
        if (d.sessionId) activeId.value = d.sessionId
      } else if (ev.event === 'follow_ups') {
        const d = ev.data as { questions?: string[]; sessionTitle?: string | null }
        followUps.value = d.questions || []
        // 后端在首轮问答后把会话标题改写为 LLM 摘要，同步侧边栏
        if (d.sessionTitle) {
          const item = sessions.value.find((x) => x.id === sid)
          if (item) item.title = d.sessionTitle
        }
      } else if (ev.event === 'error') {
        const d = ev.data as { message: string }
        errorMsg.value = d.message
        retryPayload.value = { text, attachments }
        toast.error(`问答出错：${d.message}`)
      }
    }
  } catch (e: unknown) {
    // 异常 / 主动取消 → 立即冲刷缓冲，不继续动画
    flushTypewriter()
    if (!(e instanceof DOMException && e.name === 'AbortError')) {
      errorMsg.value = errorMsg.value || errMsg(e)
      retryPayload.value = { text, attachments }
      toast.error(`问答中断：${errMsg(e)}`)
    }
  } finally {
    streamEnded = true
    // 如果打字机从未启动（无 delta 事件，如纯错误响应），直接结束
    if (!typeTimer) streaming.value = false
    deepThinking.value = false
    askAbort.value = null
    // 就地同步当前会话，不整页 reload，避免覆盖懒加载列表与滚动位置
    const cur = sessions.value.find((x) => x.id === sid)
    if (cur) {
      cur.title = cur.title || text
      cur.updatedAt = new Date().toISOString()
      cur.msgCount = (cur.msgCount ?? 0) + 1
    } else if (sessionsData.value) {
      const fresh = sessionsData.value.items.find((x) => x.id === sid)
      if (fresh) insertSession(fresh)
    }
  }
}

function stop() {
  askAbort.value?.abort()
}

/** V4：重试上一个失败的问题：移除失败的用户/助手消息对，恢复输入后复发。 */
function retryLast() {
  const p = retryPayload.value
  if (!p || streaming.value) return
  // 尾部两条即本次失败的 user + 空 assistant，移除后重发避免重复气泡
  const ms = messages.value
  if (ms.length >= 2 && ms[ms.length - 1].role !== 'user' && !ms[ms.length - 1].content) {
    messages.value = ms.slice(0, -2)
  }
  errorMsg.value = ''
  retryPayload.value = null
  inputText.value = p.text
  attached.value = p.attachments ? [...p.attachments] : []
  void send()
}

function onKeydown(e: KeyboardEvent) {
  if (e.key !== 'Enter') return
  // 发送习惯跟随个人设置（系统设置页「Enter 发送」开关）
  if (state.prefs.enterToSend !== false) {
    if (!e.shiftKey) {
      e.preventDefault()
      send()
    }
  } else if (e.ctrlKey || e.metaKey) {
    e.preventDefault()
    send()
  }
}

/* ---------- 附件（图片需视觉模型 / 文档全模型；音视频已移除） ---------- */
const MAX_ATTACH_BYTES = 20 * 1024 * 1024
// 单次附件数量上限（与后端 MAX_FILES_PER_ASK 同步）：超出前端直接拦截
const MAX_ATTACH_COUNT = 5
async function onAttach(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  for (const f of files) {
    if (attached.value.length >= MAX_ATTACH_COUNT) {
      toast.warning(`单次最多上传 ${MAX_ATTACH_COUNT} 个附件`)
      break
    }
    const kind = kindOf(f)
    if (!kind) { toast.error(`不支持的文件类型：${f.name}`); continue }
    if (f.size > MAX_ATTACH_BYTES) { toast.error(`文件过大（≤20MB）：${f.name}`); continue }
    // 视觉端点未配置时才拦截图片（带图提问会自动路由视觉模型，与所选文本模型无关）
    if (kind === 'image' && !chatVision.value) {
      toast.warning('视觉问答服务未配置，图片已忽略')
      continue
    }
    try {
      if (kind === 'document') {
        // 文档走 base64 交后端解析提取文本（不依赖视觉能力）
        const b64 = await readFileB64(f)
        attached.value.push({ kind, mimeType: f.type || 'application/octet-stream', dataB64: b64, name: f.name })
      } else {
        // 图片：优先 OSS 直传拿可访问地址；未启用则回退本地 base64
        try {
          const { url } = await uploadToOss(f, 'uploads/chat')
          attached.value.push({ kind, mimeType: f.type, url, name: f.name })
        } catch (ossErr: unknown) {
          if (errMsg(ossErr, '').includes('OSS 未启用')) {
            const b64 = await readFileB64(f)
            attached.value.push({ kind, mimeType: f.type, dataB64: b64, name: f.name })
          } else {
            throw ossErr
          }
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
  } catch (e: unknown) {
    toast.error(`反馈失败：${errMsg(e)}`)
  }
}

/* ---------- 建议 ---------- */
function pick(s: string) {
  inputText.value = s
}

/** 追问 chip：直接发送（区别于空状态卡片只填充输入框）。 */
function pickAndSend(s: string) {
  if (streaming.value) return
  inputText.value = s
  void send()
}

/* ---------- 重新生成 / 导出 / 重命名 ---------- */
const lastAiId = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    if (m.role !== 'user' && m.content) return m.id
  }
  return null
})

/** 重新生成：移除旧回答（服务端同删）后重发上一问。 */
async function regenerate(m: ChatMessage) {
  if (streaming.value || !m.messageId) return
  const idx = messages.value.findIndex((x) => x.id === m.id)
  const prev = idx > 0 ? messages.value[idx - 1] : null
  const sid = activeId.value
  if (!prev || prev.role !== 'user' || !sid) return
  try {
    await deleteMessage(m.messageId)
  } catch (e: unknown) {
    toast.error(`删除旧回答失败：${errMsg(e)}`)
    return
  }
  messages.value.splice(idx, 1)
  const aiMsg: ChatMessage = { id: genId(), role: 'assistant', content: '', thinkingSteps: [], feedback: null }
  messages.value.push(aiMsg)
  const reactiveAiMsg = messages.value[messages.value.length - 1]
  scrollToBottom(true)
  await runStream(prev.content, sid, prev.attachments ?? null, reactiveAiMsg)
}

/** 导出当前对话为 Markdown 文件。 */
function exportSession() {
  if (!messages.value.length) {
    toast.warning('没有可导出的内容')
    return
  }
  const title = activeSession.value?.title || firstQuestion.value || '对话'
  const lines: string[] = [
    `# ${title}`,
    '',
    `> 导出自知海 Knoa 智能问答 · ${new Date().toLocaleString()}`,
    '',
  ]
  for (const m of messages.value) {
    if (!m.content) continue
    lines.push(m.role === 'user' ? '## 提问' : '## 回答', '', m.content, '')
    const refs = citedSources(m)
    if (refs.length) {
      lines.push(
        '**引用来源：**',
        ...refs.map((s) => `- [${s.id}] ${s.title}（${s.kb || s.sourceType || 'kb'}）`),
        '',
      )
    }
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${title.slice(0, 30)}_${new Date().toISOString().slice(0, 10)}.md`
  a.click()
  URL.revokeObjectURL(url)
  toast.success('对话已导出')
}

async function onRenameSession(id: string, title: string) {
  try {
    await renameSession(id, title)
    const item = sessions.value.find((x) => x.id === id)
    if (item) item.title = title
  } catch (e: unknown) {
    toast.error(`重命名失败：${errMsg(e)}`)
  }
}

/* ---------- 无来源引导 ---------- */
function prevUserOf(m: ChatMessage): ChatMessage | null {
  const idx = messages.value.findIndex((x) => x.id === m.id)
  const prev = idx > 0 ? messages.value[idx - 1] : null
  return prev && prev.role === 'user' ? prev : null
}

/** 无来源提示仅对最新一条回答显示，且排除简短问候。 */
function showNoSourceHint(m: ChatMessage): boolean {
  if (streaming.value || m.id !== lastAiId.value || m.sources?.length || !m.messageId) return false
  const prev = prevUserOf(m)
  if (!prev || prev.content.length < 8) return false
  // 带图提问的回答不依赖知识库来源，不提示「未找到来源」
  return !prev.attachments?.some(a => a.kind === 'image')
}

/** 引用来源只展示模型实际引用（[n] 标记）的召回，弱相关未被引用的不陈列。
 *  流式期间 citations 未定（undefined）先展示全量，done/历史回显后按交集收窄。 */
function citedSources(m: ChatMessage): SourceItem[] {
  if (!m.sources?.length) return []
  if (m.citations === undefined) return m.sources
  const cited = new Set(m.citations)
  return m.sources.filter(s => cited.has(s.id))
}

/** 无来源：把上一问填回输入框供用户换种问法。 */
function rephrase(m: ChatMessage) {
  const prev = prevUserOf(m)
  if (prev) inputText.value = prev.content
}

/** 无来源：解除知识库范围限制后重新生成。 */
async function retryAllKb(m: ChatMessage) {
  selectedKb.value = ''
  await regenerate(m)
}

const route = useRoute()
const router = useRouter()

// 跳转参数消费：?session= 打开对应对话；?q= + ?kb= 预填问题并预选库
// （来自检索记录页「继续追问」与图谱「提问」按钮）。
// keep-alive 下页面不再随导航重建，参数须在每次激活时消费；
// 消费后把 URL 归一成干净的 /chat，避免旧参数在下次激活时重放。
let queryConsumed = false
async function consumeRouteQuery() {
  const sid = typeof route.query.session === 'string' ? route.query.session : ''
  const qParam = typeof route.query.q === 'string' ? route.query.q : ''
  const kbParam = typeof route.query.kb === 'string' ? route.query.kb : ''
  if (!sid && !qParam && !kbParam) return
  if (sid) await selectSession(sid)
  if (qParam) inputText.value = qParam
  if (kbParam) selectedKb.value = kbParam
  router.replace({ path: '/chat' })
}

onMounted(async () => {
  await loadSessions()
  void loadKbOptions()
  void loadSuggested()
  await consumeRouteQuery()
  queryConsumed = true
})
// keep-alive 重新激活：重挂全局监听；首挂载由 onMounted 消费参数，此处只处理后续激活
onActivated(() => {
  document.addEventListener('mousedown', onHeadOutside)
  window.addEventListener('keydown', onHeadEsc)
  if (queryConsumed) void consumeRouteQuery()
})
watch(messages, () => scrollToBottom(), { deep: false })
</script>

<template>
  <div class="chat-page">
    <!-- ====== 对话区（会话列表移入消息区父容器，见 chat-body） ====== -->
    <main class="chat-main">
      <div class="card chat-panel">
      <!-- 头部：会话条（左=侧栏切换+小标题，右=⋯菜单+新建对话） -->
      <header class="chat-header">
        <div class="chat-head-left">
          <button
            class="head-icon-btn"
            :title="sidebarCollapsed ? '展开对话列表' : '收起对话列表'"
            @click="setSidebarCollapsed(!sidebarCollapsed)"
          >
            <Icon :name="sidebarCollapsed ? 'panel-left-open' : 'collapse'" :size="16" />
          </button>
          <span class="chat-session-title" :title="activeSession?.title || ''">
            <Icon v-if="activeSession?.pinned" name="pin" :size="11" class="title-pin" />
            <span class="title-text">{{ activeSession?.title || '新对话' }}</span>
          </span>
        </div>
        <div class="chat-head-actions">
          <button class="head-icon-btn head-more" title="更多操作" @click="openHeadMenu">
            <Icon name="more" :size="16" />
          </button>
          <button class="btn btn-primary btn-sm" @click="newChat">
            <Icon name="plus" :size="14" />
            <span>新建对话</span>
          </button>
        </div>
      </header>

      <!-- 头部 ⋯ 浮动菜单：低频操作收敛于此 -->
      <Teleport to="body">
        <div v-if="headMenuOpen" class="head-menu" :style="{ top: headMenuPos.top + 'px', left: headMenuPos.left + 'px' }">
          <button class="head-menu-item" @click="headExport">
            <Icon name="export" :size="14" />
            <span>导出 Markdown</span>
          </button>
          <button class="head-menu-item danger" @click="headClear">
            <Icon name="trash" :size="14" />
            <span>清空对话</span>
          </button>
        </div>
      </Teleport>

      <!-- 消息区 + 输入区（共用灰色背景）；会话列表为左列，对话内容为右列 -->
      <div class="chat-body">
      <ChatSessionList
        v-if="!sidebarCollapsed"
        :sessions="sessions"
        :total="sessionTotal"
        :active-id="activeId"
        :loading-more="sessionLoadingMore"
        :all-loaded="allSessionsLoaded"
        @select="selectSession"
        @remove="onDeleteSession"
        @rename="onRenameSession"
        @pin="onPinSession"
        @load-more="loadSessions(true)"
      />

      <div class="chat-convo">
      <!-- 消息区 -->
      <div class="messages-area" ref="scrollRef" @scroll="onMsgScroll">
        <!-- 空状态（hero） -->
        <div v-if="!messages.length" class="empty-hero">
          <div class="empty-orb">
            <Icon name="sparkles" :size="28" />
          </div>
          <h2 class="empty-title">向企业知识库提问</h2>
          <p class="empty-sub">基于内部文档检索作答，可附图片进行多模态提问。回答均标注引用来源。</p>
          <div class="empty-suggest">
            <button v-for="(s, i) in suggested" :key="i" class="empty-card" :title="s" @click="pick(s)">
              <Icon name="arrow-up-right" :size="15" class="empty-card-icon" />
              <span class="empty-card-text">{{ s }}</span>
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

          <div class="msg-bubble" :class="{ 'has-tts': m.role !== 'user' && auth.user?.ttsEnabled && m.content }">
            <!-- 语音播报（右上角） -->
            <button
              v-if="m.role !== 'user' && auth.user?.ttsEnabled && m.content"
              class="tts-corner act-btn"
              :class="{ on: playingId === m.id }"
              :title="playingId === m.id ? '停止播报' : '朗读回答'"
              @click="speak(m.id, m.content)"
            >
              <Icon :name="playingId === m.id ? 'square' : 'volume'" :size="14" />
            </button>
            <!-- 用户附件 -->
            <div class="attach-thumbs" v-if="m.role === 'user' && m.attachments?.length">
              <template v-for="(a, i) in m.attachments" :key="i">
                <img v-if="a.kind === 'image'" :src="attachSrc(a)" class="attach-thumb" />
                <audio v-else-if="a.kind === 'audio'" :src="attachSrc(a)" controls class="attach-media" />
                <video v-else-if="a.kind === 'video'" :src="attachSrc(a)" controls class="attach-media" />
                <span v-else-if="a.kind === 'document'" class="attach-badge attach-doc"><Icon name="doc" :size="12" />{{ a.name || '文档' }}</span>
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

            <!-- 正文（Markdown 渲染，[N] 角标可点击联动来源卡） -->
            <div v-if="m.content" class="answer-body md" v-html="renderAnswer(m.content)" @click="onCiteClick"></div>
            <div v-else-if="streaming" class="answer-loading">
              <span class="dot" /><span class="dot" /><span class="dot" />
              <span v-if="deepThinking" class="busy-hint">深度思考中…</span>
            </div>

            <!-- 引用文档（仅模型实际引用的来源） -->
            <div v-if="m.role !== 'user' && citedSources(m).length" class="refs">
              <div class="refs-label">
                <Icon name="quote" :size="14" />
                <span>引用来源（{{ citedSources(m).length }}）</span>
              </div>
              <div class="refs-grid">
                <div v-for="(s, i) in citedSources(m)" :key="s.id ?? i" class="ref-card" :data-ref-id="s.id" :class="{ 'ref-clickable': s.kbId && s.docId }" @click="openDocDetail(s)" :title="s.kbId && s.docId ? '点击查看文档详情' : undefined">
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

            <!-- 无来源引导：检索不到时提示换问法 / 放宽范围 -->
            <div v-if="m.role !== 'user' && showNoSourceHint(m)" class="no-source-hint">
              <Icon name="info" :size="13" />
              <span>未在知识库找到相关来源，可以试试：</span>
              <button class="chip chip-mini" @click="rephrase(m)">换种问法</button>
              <button v-if="selectedKb" class="chip chip-mini" @click="retryAllKb(m)">搜全部知识库</button>
            </div>

            <!-- 错误 -->
            <div v-if="m.role !== 'user' && errorMsg && !m.content" class="answer-error">
              <Icon name="alert" :size="14" />
              <span>{{ errorMsg }}</span>
              <button v-if="retryPayload" class="btn-retry" @click="retryLast">重试</button>
            </div>

            <!-- 反馈 + 操作 -->
            <div v-if="m.role !== 'user' && m.messageId && m.content" class="msg-actions">
              <span class="msg-actions-divider" />
              <button class="act-btn" title="复制回答" @click="copyAnswer(m)">
                <Icon name="copy" :size="14" />
              </button>
              <button v-if="m.id === lastAiId" class="act-btn" title="重新生成" @click="regenerate(m)">
                <Icon name="refresh" :size="14" />
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

      <!-- 建议追问（优先用后端 follow_ups 事件下发的动态追问） -->
      <div class="suggest-row" v-if="!streaming && messages.length">
        <span class="suggest-label">你可能还想问</span>
        <button v-for="(s, i) in (followUps.length ? followUps : suggested)" :key="i" class="chip" @click="pickAndSend(s)">{{ s }}</button>
      </div>

      <!-- 输入区（仅对话视图显示） -->
      <div class="composer">
        <!-- 附件紧凑条：仅有附件时才占一行，无附件时把高度让给对话区 -->
        <div v-if="attached.length" class="attach-strip">
          <div v-for="(a, i) in attached" :key="i" class="attach-chip" :class="'kind-' + a.kind">
            <img v-if="a.kind === 'image'" :src="attachSrc(a)" class="attach-thumb" :title="a.name || '附件'" />
            <template v-else>
              <span class="attach-doc-icon"><Icon name="doc" :size="11" /></span>
              <span class="attach-name" :title="a.name || '文档'">{{ a.name || '文档' }}</span>
            </template>
            <button class="attach-x" title="移除附件" @click="removeAttach(i)"><Icon name="close" :size="12" /></button>
          </div>
        </div>

        <textarea
          ref="inputRef"
          v-model="inputText"
          class="composer-input"
          rows="1"
          :placeholder="state.prefs.enterToSend !== false ? '输入问题，Shift + Enter 换行，Enter 发送' : '输入问题，Enter 换行，Ctrl + Enter 发送'"
          @keydown="onKeydown"
        ></textarea>

        <div class="composer-bar">
          <div class="composer-left">
            <CustomSelect v-model="selectedKb" :options="kbSelectOptions" width="170px">
              <template #prefix>
                <Icon name="folder" :size="13" class="scope-prefix" />
              </template>
            </CustomSelect>
            <!-- 字数计数置于下拉框右侧同行，不撑高底部栏 -->
            <span class="composer-count" :class="{ over: inputText.length > QUESTION_MAX_LEN }">{{ inputText.length }} / {{ QUESTION_MAX_LEN }}</span>
          </div>
          <div class="composer-right">
            <label class="composer-attach" title="附加附件">
              <Icon name="attach" :size="17" />
              <input type="file" :accept="acceptAttr" multiple class="file-hidden" @change="onAttach" />
            </label>
            <button v-if="streaming" class="btn btn-ghost" @click="stop">
              <Icon name="square" :size="13" />
              <span>停止</span>
            </button>
            <button v-else class="btn btn-primary composer-send" :disabled="!inputText.trim() || inputText.length > QUESTION_MAX_LEN" title="发送" @click="send">
              <Icon name="arrow-up" :size="16" />
            </button>
          </div>
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
    :loading="deletingSession"
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

  <!-- 文档详情弹框（拆分组件） -->
  <DocDetailModal :doc="docDetail" :loading="docDetailLoading" :snippet="docDetailSnippet" @close="docDetail = null" />
</template>

<style scoped>
.chat-page {
  display: flex;
  height: calc(100vh - var(--topbar-h) - 40px);
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


/* ============ 对话主区 ============ */
.chat-main {
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
  flex-direction: row;
  gap: 10px;
  flex: 1;
  min-height: 0;
}
/* 对话内容右列（消息区 + 追问 + 输入区）：与会话列表并列的兄弟卡片 */
.chat-convo {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-subtle);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 10px;
}
.chat-head-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
/* 头部图标按钮（侧栏切换 / ⋯ 菜单）：固定位置，收起展开同一处 */
.head-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  flex: none;
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  transition: all var(--dur-fast) var(--ease-out);
}
.head-icon-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
/* 小号会话标题：不抢戏，长对话/侧栏收起时提供上下文锚点 */
.chat-session-title {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}
.title-pin { flex: none; color: var(--brand); }
.title-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* 头部 ⋯ 浮动菜单（与侧栏三点菜单同款样式） */
.head-menu {
  position: fixed;
  z-index: 300;
  width: 160px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-float);
}
.head-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-primary);
  transition: background var(--dur-fast) var(--ease-out);
}
.head-menu-item:hover { background: var(--bg-hover); }
.head-menu-item.danger { color: var(--danger); }
.head-menu-item.danger:hover { background: var(--danger-soft); }
.chat-head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
/* 工具栏按钮跟随全局 .btn 系统（36px），圆形发送按钮需宽高一致 */

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
  border-radius: var(--radius-xl);
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
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
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
.empty-card-text {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

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
  border-radius: var(--radius-md);
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
  border-radius: var(--radius-sm) var(--radius-lg) var(--radius-lg) var(--radius-lg);
  box-shadow: var(--shadow-card);
  flex: 1;
}
.msg-row.user-msg .msg-bubble {
  background: var(--brand);
  color: var(--text-on-brand);
  border-radius: var(--radius-lg) var(--radius-sm) var(--radius-lg) var(--radius-lg);
}
.msg-row.ai-msg .msg-bubble.has-tts {
  position: relative;
  padding-right: 46px;
}
.tts-corner {
  position: absolute;
  top: 15px;
  right: 10px;
  width: 28px;
  height: 28px;
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

.btn-retry {
  margin-left: 4px;
  padding: 2px 10px;
  font-size: 12px;
  color: var(--brand);
  background: var(--brand-soft);
  border: none;
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition: background var(--dur-fast);
}
.btn-retry:hover { background: var(--bg-hover); }

/* ============ Markdown 渲染（answer-body）============ */
/* 气泡是 pre-wrap（用户消息纯文本需要），Markdown 渲染必须复位为 normal，
   否则 HTML 标签间的换行会被当内容渲染出大量空行 */
.answer-body.md { white-space: normal; font-size: 14px; }
.answer-body.md :deep(> :first-child) { margin-top: 0; }
.answer-body.md :deep(> :last-child) { margin-bottom: 0; }
.answer-body.md :deep(p) { margin: 0 0 12px; }
/* 标题：拉开字号梯度形成视觉锚点，避免和正文混成一片 */
.answer-body.md :deep(h1), .answer-body.md :deep(h2), .answer-body.md :deep(h3), .answer-body.md :deep(h4) {
  font-weight: 700; color: var(--text-primary); line-height: 1.45;
}
.answer-body.md :deep(h1) { font-size: 16.5px; margin: 20px 0 10px; }
.answer-body.md :deep(h2) { font-size: 15px; margin: 18px 0 8px; }
.answer-body.md :deep(h3), .answer-body.md :deep(h4) { font-size: 14px; margin: 14px 0 6px; }
/* 列表：品牌色圆点 + 宽松行距，嵌套列表收紧 */
.answer-body.md :deep(ul), .answer-body.md :deep(ol) { margin: 0 0 12px; padding-left: 20px; }
.answer-body.md :deep(li) { margin: 5px 0; padding-left: 2px; }
.answer-body.md :deep(ul > li)::marker { color: var(--brand); }
.answer-body.md :deep(ol > li)::marker { color: var(--text-tertiary); font-weight: 600; }
.answer-body.md :deep(li > p) { margin: 0; }
.answer-body.md :deep(li > ul), .answer-body.md :deep(li > ol) { margin: 4px 0; }
/* 加粗降为 600：模型爱滥加粗，700 大片黑体显得噪 */
.answer-body.md :deep(strong) { font-weight: 600; color: var(--text-primary); }
/* 行内代码：去边框只留浅底，减少碎片感 */
.answer-body.md :deep(code) {
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', Consolas, monospace);
  font-size: 0.88em;
  background: var(--bg-subtle);
  border-radius: 5px;
  padding: 2px 6px;
  color: var(--text-secondary);
}
/* 代码块：固定深色底（深浅主题一致），更接近 IDE 观感 */
.answer-body.md :deep(pre) {
  background: #1f2330;
  border: none;
  border-radius: var(--radius-md);
  padding: 14px 16px;
  margin: 0 0 14px;
  overflow-x: auto;
}
.answer-body.md :deep(pre code) {
  background: none; border: none; padding: 0;
  color: #e6e9f0; font-size: 12.5px; line-height: 1.65;
}
.answer-body.md :deep(blockquote) {
  margin: 0 0 12px;
  padding: 8px 14px;
  border-left: 3px solid var(--brand);
  background: var(--brand-soft);
  color: var(--text-secondary);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
.answer-body.md :deep(blockquote p) { margin: 0; }
/* 表格：横向滚动 + 斑马纹 + 只留横线，去掉田字格 */
.answer-body.md :deep(table) {
  display: block; overflow-x: auto;
  border-collapse: collapse;
  margin: 0 0 14px; font-size: 13px;
  max-width: 100%;
}
.answer-body.md :deep(th), .answer-body.md :deep(td) {
  border: 1px solid var(--border); padding: 7px 12px; text-align: left;
}
.answer-body.md :deep(th) { background: var(--bg-subtle); font-weight: 600; font-size: 12.5px; white-space: nowrap; }
.answer-body.md :deep(tbody tr:nth-child(even)) { background: var(--bg-subtle); }
.answer-body.md :deep(a) { color: var(--brand); text-decoration: none; border-bottom: 1px solid transparent; }
.answer-body.md :deep(a:hover) { border-bottom-color: var(--brand); }
.answer-body.md :deep(hr) { border: none; border-top: 1px solid var(--border); margin: 16px 0; }

/* 引用角标 chip：正文 [N] → 点击滚动高亮同号来源卡。
   chip 由 v-html 动态注入（无 data-v 属性），必须用 :deep() 穿透 scoped，
   否则样式失效、被全局 button reset 还原成裸数字文本 */
.answer-body.md :deep(.cite-chip) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  margin: 0 2px;
  border-radius: 5px;
  border: 1px solid var(--brand-ring);
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  vertical-align: 1px;
  transition: all var(--dur-fast) var(--ease-out);
}
.answer-body.md :deep(.cite-chip:hover) { background: var(--brand); color: #fff; border-color: var(--brand); }
.ref-flash { animation: ref-flash 1.4s var(--ease-out); }
@keyframes ref-flash {
  0%, 55% { border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); }
  100% { box-shadow: none; }
}

/* 深度思考提示（ping 驱动） */
.busy-hint {
  margin-left: 6px;
  font-size: 12px;
  color: var(--text-tertiary);
  animation: blink 1.3s infinite ease-in-out;
}

/* 无来源引导 */
.no-source-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding: 9px 12px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-subtle);
  font-size: 12px;
  color: var(--text-tertiary);
}
.chip-mini { padding: 3px 10px; font-size: 11.5px; }

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
  border-radius: var(--radius-md);
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
  padding: 12px 14px;
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
/* 附件紧凑条：并入底部操作栏（回形针后）横排展示，溢出横向滚动，
   不占独立行，把高度让给对话区 */
.attach-strip {
  display: flex; align-items: center; gap: 6px;
  flex: 1; min-width: 0;
  overflow-x: auto; padding: 2px;
  scrollbar-width: thin;
}
.attach-chip {
  flex: none; display: inline-flex; align-items: center; gap: 5px;
  max-width: 170px;
  padding: 3px 5px 3px 6px;
  border-radius: var(--radius-md);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
}
.attach-doc-icon {
  flex: none; width: 16px; height: 16px; border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  background: color-mix(in srgb, var(--brand) 14%, transparent);
  color: var(--brand);
}
.attach-name {
  font-size: 11px; line-height: 1; color: var(--text-secondary);
  max-width: 110px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.attach-chip .attach-thumb { width: 20px; height: 20px; border-radius: 5px; }
.attach-chip .attach-x {
  flex: none; width: 20px; height: 20px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-secondary);
  transition: color var(--dur-fast), background var(--dur-fast), transform var(--dur-fast);
}
.attach-chip .attach-x:hover {
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 18%, transparent);
  transform: scale(1.08);
}
/* 消息气泡内附件缩略图 / 音视频（独立尺寸，不受紧凑条影响） */
.attach-thumb { width: 50px; height: 50px; border-radius: var(--radius-md); object-fit: cover; border: 1px solid var(--border); }
.attach-media { width: 200px; max-width: 60vw; border-radius: var(--radius-md); border: 1px solid var(--border); }
.attach-badge { display: inline-flex; padding: 4px 10px; border-radius: var(--radius-md); background: var(--bg-subtle); color: var(--text-secondary); font-size: 12px; }
.attach-doc { gap: 5px; align-items: center; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.attach-doc .icon { flex: none; }

.composer-input {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  min-height: 45px;
  max-height: 112px;
  overflow-y: auto;
  font-family: inherit;
  padding: 11px 2px;
}
.composer-input::placeholder { color: var(--text-placeholder); }

.composer-bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-top: 10px;
}
.attach-thumb { width: 50px; height: 50px; border-radius: var(--radius-md); object-fit: cover; border: 1px solid var(--border); }
.attach-media { width: 200px; max-width: 60vw; border-radius: var(--radius-md); border: 1px solid var(--border); }
.composer-left { display: flex; align-items: center; gap: 12px; }
/* 附件条置顶时与输入框的间距；知识库下拉移入底部栏后压缩 trigger 高度 */
.composer > .attach-strip { margin-bottom: 8px; }
.composer-left :deep(.c-select-trigger) { height: 28px; font-size: 12.5px; }
/* 知识库下拉框内前置文件夹图标 */
.scope-prefix { flex: none; color: var(--text-tertiary); }
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
.composer-count { font-size: 12px; color: var(--text-tertiary); line-height: 1; }
.composer-count.over { color: var(--danger); }
.composer-right { display: flex; align-items: center; gap: 20px; }
/* 发送按钮：圆形纯图标（上箭头），与回形针同高，不额外撑高底部栏 */
.composer-send { width: var(--btn-h-md); padding: 0; border-radius: 50%; }

@keyframes fade-up {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin 0.9s linear infinite; }

@media (max-width: 720px) {
  .empty-suggest { grid-template-columns: 1fr; }
}

/* 引用卡片可点击态（详情弹框本体在 DocDetailModal） */
.ref-clickable {
  cursor: pointer;
}
.ref-clickable:hover {
  border-color: var(--brand);
  transform: translateY(-2px);
  box-shadow: var(--shadow-float);
}

</style>
