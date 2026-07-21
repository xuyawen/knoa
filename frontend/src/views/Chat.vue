<script setup lang="ts">
// AI 智能问答 — 按 640(5).png 截图 1:1 还原，接真实 SSE 流式问答。
// section 由路由决定（new/history/records/model）。
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import Icon from '@/components/ui/Icon.vue'
import { useToastStore } from '@/stores/toast'
import {
  getSessions,
  createSession,
  getSession,
  deleteSession,
  streamAsk,
  submitFeedback,
  deleteFeedback,
} from '@/api'
import type {
  ChatSession,
  ChatMessage,
  SessionMessage,
  ThinkingStep,
  SourceItem,
  ChatAttachment,
} from '@/types/api'

const toast = useToastStore()
const router = useRouter()

const props = defineProps<{ section?: string }>()
const section = computed(() => props.section ?? 'new')

// 模型配置（本地持久化，后端暂未提供全局模型设置接口）
const MODEL_KEY = 'knoa.chat.model'
const modelName = ref(localStorage.getItem(MODEL_KEY + '.name') || 'agnes-2.0-flash')
const temperature = ref(Number(localStorage.getItem(MODEL_KEY + '.temp')) || 0.3)
const maxTokens = ref(Number(localStorage.getItem(MODEL_KEY + '.max')) || 2000)
function saveModel() {
  localStorage.setItem(MODEL_KEY + '.name', modelName.value)
  localStorage.setItem(MODEL_KEY + '.temp', String(temperature.value))
  localStorage.setItem(MODEL_KEY + '.max', String(maxTokens.value))
  toast.success('模型配置已保存')
}

// 从「问答记录」打开某会话：载入消息并切回对话视图
function openSession(id: string) {
  selectSession(id)
  router.push('/chat/new')
}

const sessions = ref<ChatSession[]>([])
const activeId = ref<string | null>(null)
const messages = ref<ChatMessage[]>([])
const streaming = ref(false)
const inputText = ref('')
const errorMsg = ref('')
const askAbort = ref<AbortController | null>(null)
const attached = ref<ChatAttachment[]>([])
const showThinking = ref(false)

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

/* ---------- 会话 ---------- */
async function loadSessions() {
  try {
    sessions.value = await getSessions()
  } catch (e: any) {
    toast.error(`加载会话失败：${e?.message || e}`)
  }
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
    sessions.value = [s, ...sessions.value]
    activeId.value = s.id
    messages.value = []
    errorMsg.value = ''
  } catch (e: any) {
    toast.error(`新建会话失败：${e?.message || e}`)
  }
}

async function onDeleteSession(id: string) {
  if (!confirm('确认删除该会话？删除后无法恢复。')) return
  try {
    await deleteSession(id)
    sessions.value = sessions.value.filter((s) => s.id !== id)
    if (activeId.value === id) {
      activeId.value = null
      messages.value = []
    }
    toast.success('会话已删除')
  } catch (e: any) {
    toast.error(`删除失败：${e?.message || e}`)
  }
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
      sessions.value = [s, ...sessions.value]
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
    loadSessions() // 刷新标题 / 时间
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

/* ---------- 附件（多模态图片） ---------- */
async function onAttach(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  for (const f of files) {
    if (!f.type.startsWith('image/')) continue
    try {
      const b64 = await readFileB64(f)
      attached.value.push({ kind: 'image', mimeType: f.type, dataB64: b64, name: f.name })
    } catch {
      toast.error(`读取图片失败：${f.name}`)
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

onMounted(async () => {
  await loadSessions()
  // 历史会话分区：默认打开最新一条会话做只读浏览
  if (section.value === 'history' && sessions.value.length && !activeId.value) {
    selectSession(sessions.value[0].id)
  }
})
watch(messages, scrollToBottom, { deep: false })
</script>

<template>
  <div class="chat-page" v-if="section === 'new' || section === 'history'">
    <!-- ====== 左栏：会话列表 ====== -->
    <aside class="chat-sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">会话列表</span>
        <Icon name="list" :size="16" class="sidebar-icon-btn" />
      </div>
      <button v-if="section === 'new'" class="btn btn-new-chat" @click="newChat">
        <Icon name="plus" :size="14" /> 新建对话
      </button>
      <div class="conv-list">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="conv-item"
          :class="{ active: s.id === activeId }"
          @click="selectSession(s.id)"
        >
          <div class="conv-q">{{ s.title || '（新会话）' }}</div>
          <div class="conv-meta">
            <span class="conv-time">{{ s.updatedAt ? s.updatedAt.slice(5, 10) : '' }}</span>
            <span class="conv-count">{{ s.msgCount }} 条</span>
          </div>
          <button class="conv-del" title="删除会话" @click.stop="onDeleteSession(s.id)">
            <Icon name="trash" :size="13" />
          </button>
        </div>
      </div>
    </aside>

    <!-- ====== 中栏：对话区 ====== -->
    <main class="chat-main">
      <!-- 头部 -->
      <div class="chat-header">
        <h3 class="chat-question">{{ firstQuestion || 'AI 智能问答' }}</h3>
        <button class="btn-clear-chat" @click="messages = []">
          <Icon name="close" :size="13" /> 清空对话
        </button>
      </div>

      <!-- 消息区 -->
      <div class="messages-area" ref="scrollRef">
        <!-- 空状态 -->
        <div v-if="!messages.length" class="empty-state">
          <div class="empty-avatar"><Icon name="chat" :size="26" /></div>
          <p class="empty-title">有什么可以帮你的？</p>
          <p class="empty-sub">基于企业知识库为你检索作答，可附图片进行多模态提问。</p>
        </div>

        <template v-for="m in messages" :key="m.id">
          <!-- 用户 -->
          <div v-if="m.role === 'user'" class="msg-row user-msg">
            <div class="msg-bubble user-bubble">
              <div class="attach-thumbs" v-if="m.attachments?.length">
                <img v-for="(a, i) in m.attachments" :key="i" :src="`data:${a.mimeType};base64,${a.dataB64}`" class="attach-thumb" />
              </div>
              {{ m.content }}
            </div>
          </div>

          <!-- AI -->
          <div v-else class="msg-row ai-msg">
            <div class="msg-avatar ai-avatar"><Icon name="chat" :size="16" /></div>
            <div class="msg-bubble">
              <!-- 思考过程 -->
              <div v-if="m.thinkingSteps?.length" class="thinking">
                <button class="thinking-toggle" @click="showThinking = !showThinking">
                  <Icon name="sparkles" :size="13" />
                  AI 思考过程（{{ m.thinkingSteps.length }} 步）
                  <Icon name="chevron-down" :size="11" :class="{ rotated: showThinking }" />
                </button>
                <ul v-if="showThinking" class="thinking-list">
                  <li v-for="t in m.thinkingSteps" :key="t.step">
                    <span class="think-action">{{ t.action }}</span>
                    <span class="think-detail">{{ t.detail }}</span>
                  </li>
                </ul>
              </div>

              <!-- 正文 -->
              <div v-if="m.content" class="answer-body">{{ m.content }}</div>
              <div v-else-if="streaming" class="answer-loading">
                <span class="dot" /><span class="dot" /><span class="dot" />
              </div>

              <!-- 引用文档 -->
              <div v-if="m.sources?.length" class="refs-section">
                <div class="refs-label">引用文档（{{ m.sources.length }}）</div>
                <div class="refs-list">
                  <div v-for="(s, i) in m.sources" :key="s.id ?? i" class="ref-file-card">
                    <div class="rfc-icon" :class="`src-${s.sourceType || 'kb'}`">
                      <Icon :name="s.sourceType === 'web' ? 'globe' : s.sourceType === 'graph' ? 'node' : 'doc'" :size="18" />
                    </div>
                    <div class="rfc-info">
                      <div class="rfc-name">{{ s.title }}</div>
                      <div class="rfc-meta-row">
                        <span>{{ s.kb || '知识库' }} · {{ s.confidence ? Math.round(s.confidence * 100) + '%' : '相关' }}</span>
                        <span>{{ s.snippet ? '3页' : '—' }} · {{ new Date().toLocaleDateString('zh-CN') }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 反馈 + 错误 -->
              <div v-if="errorMsg && !m.content" class="answer-error">{{ errorMsg }}</div>
              <div v-if="m.messageId && m.content" class="feedback-row">
                <button class="fb-btn" :class="{ on: m.feedback === 'up' }" @click="onFeedback(m, 'up')" title="有用">
                  <Icon name="check" :size="14" />
                </button>
                <button class="fb-btn" :class="{ on: m.feedback === 'down' }" @click="onFeedback(m, 'down')" title="没用">
                  <Icon name="close" :size="14" />
                </button>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- 建议追问 -->
      <div class="suggest-row" v-if="!streaming">
        <span class="suggest-label">你可能还想问</span>
        <button v-for="(s, i) in suggested" :key="i" class="chip" @click="pick(s)">{{ s }}</button>
      </div>

      <!-- 输入区（仅对话视图显示） -->
      <div class="input-area" v-if="section === 'new'">
        <div v-if="attached.length" class="attach-preview">
          <div v-for="(a, i) in attached" :key="i" class="attach-preview-item">
            <img :src="`data:${a.mimeType};base64,${a.dataB64}`" class="attach-thumb" />
            <button class="attach-remove" @click="removeAttach(i)"><Icon name="close" :size="10" /></button>
          </div>
        </div>
        <textarea
          v-model="inputText"
          placeholder="请输入问题，Shift + Enter 换行"
          rows="2"
          class="chat-input"
          @keydown="onKeydown"
        ></textarea>
        <div class="input-bar">
          <div class="input-left">
            <label class="attach-btn" title="附图片">
              <Icon name="attach" :size="17" />
              <input type="file" accept="image/*" multiple class="file-hidden" @change="onAttach" />
            </label>
            <span class="char-count">{{ inputText.length }} / 2000</span>
          </div>
          <div class="input-actions">
            <button v-if="streaming" class="btn btn-ghost send-btn" @click="stop">
              <Icon name="close" :size="14" /> 停止
            </button>
            <button v-else class="btn btn-primary send-btn" :disabled="!inputText.trim()" @click="send">
              <Icon name="send" :size="15" /> 发送
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>

    <!-- ====== 问答记录 ====== -->
    <template v-else-if="section === 'records'">
      <div class="secondary-page">
        <h2 class="page-title">问答记录</h2>
        <div class="card records-card">
          <table class="records-table">
            <thead>
              <tr><th>会话</th><th>问答数</th><th>最近更新</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="s in sessions" :key="s.id">
                <td class="col-name">{{ s.title || '（新会话）' }}</td>
                <td>{{ s.msgCount }}</td>
                <td class="col-time">{{ s.updatedAt ? s.updatedAt.slice(0, 10) : '—' }}</td>
                <td><button class="link-btn" @click="openSession(s.id)">查看对话</button></td>
              </tr>
              <tr v-if="!sessions.length">
                <td colspan="4" class="empty-hint">暂无会话记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- ====== 模型配置 ====== -->
    <template v-else>
      <div class="secondary-page">
        <h2 class="page-title">模型配置</h2>
        <div class="card model-card">
          <div class="panel-head"><span class="panel-title">问答模型</span></div>
          <p class="model-note">当前后端统一使用 agnes 推理模型；以下配置为本地偏好，便于后续接入多模型路由。</p>
          <div class="model-field">
            <label>模型</label>
            <select v-model="modelName" class="select">
              <option value="agnes-2.0-flash">agnes-2.0-flash（快）</option>
              <option value="agnes-2.0-pro">agnes-2.0-pro（强）</option>
              <option value="gpt-4o">gpt-4o</option>
            </select>
          </div>
          <div class="model-field">
            <label>温度（创造性）</label>
            <div class="field-row">
              <input type="range" min="0" max="1" step="0.1" v-model.number="temperature" class="range" />
              <span class="field-val">{{ temperature.toFixed(1) }}</span>
            </div>
          </div>
          <div class="model-field">
            <label>最大生成长度</label>
            <select v-model.number="maxTokens" class="select">
              <option :value="1000">1000</option>
              <option :value="2000">2000</option>
              <option :value="4000">4000</option>
            </select>
          </div>
          <button class="btn btn-primary" @click="saveModel">保存配置</button>
        </div>
      </div>
    </template>
</template>

<style scoped>
.chat-page {
  display: flex;
  gap: 0;
  height: calc(100vh - 58px - 48px);
  min-height: 520px;
}
.chat-page :deep(.file-hidden) {
  position: absolute;
  inset: 0;
  opacity: 0;
  width: 100%;
  cursor: pointer;
}

/* ---- 会话侧栏 ---- */
.chat-sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg-surface);
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 16px 12px;
}
.sidebar-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}
.sidebar-icon-btn { color: var(--text-tertiary); cursor: pointer; }

.btn-new-chat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: calc(100% - 24px);
  margin: 0 auto 10px;
  height: 36px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  font-size: 13px;
  font-weight: 500;
  color: var(--brand);
  cursor: pointer;
  font-family: inherit;
  transition: all var(--dur-fast);
}
.btn-new-chat:hover { border-color: var(--brand); background: var(--brand-soft); }

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}
.conv-item {
  position: relative;
  padding: 11px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--dur-fast);
  border-left: 3px solid transparent;
  margin-bottom: 2px;
}
.conv-item:hover { background: var(--bg-hover); }
.conv-item.active {
  background: var(--brand-soft);
  border-left-color: var(--brand);
}
.conv-q {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.35;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 18px;
}
.conv-meta { display: flex; gap: 8px; font-size: 11px; color: var(--text-tertiary); }
.conv-del {
  position: absolute;
  top: 10px;
  right: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  opacity: 0;
  transition: all var(--dur-fast);
}
.conv-item:hover .conv-del { opacity: 1; }
.conv-del:hover { background: var(--bg-hover); color: #DC2626; }

/* ---- 对话主区 ---- */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border);
}
.chat-question {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.btn-clear-chat {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
}
.btn-clear-chat:hover { background: var(--bg-hover); }

/* ---- 消息区 ---- */
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.empty-state {
  margin: auto;
  text-align: center;
  color: var(--text-tertiary);
  max-width: 360px;
}
.empty-avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--brand-soft);
  color: var(--brand);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 14px;
}
.empty-title { font-size: 16px; font-weight: 700; color: var(--text-primary); margin: 0 0 6px; }
.empty-sub { font-size: 13px; line-height: 1.6; margin: 0; }

.msg-row { display: flex; gap: 12px; max-width: 820px; }
.user-msg { justify-content: flex-end; }
.ai-msg { align-items: flex-start; }
.msg-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
  margin-top: 3px;
}
.ai-avatar { background: var(--brand); }

.msg-bubble {
  padding: 14px 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
.user-bubble {
  background: var(--brand);
  color: #fff;
  border-color: var(--brand);
  border-radius: var(--radius-lg) 4px var(--radius-lg) var(--radius-lg);
}
.ai-msg .msg-bubble {
  background: var(--bg-surface);
  border-radius: 4px var(--radius-lg) var(--radius-lg) var(--radius-lg);
  flex: 1;
}

/* 思考过程 */
.thinking {
  margin-bottom: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-subtle);
  overflow: hidden;
}
.thinking-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
}
.thinking-toggle .chevron-down { margin-left: auto; transition: transform var(--dur-fast); color: var(--text-tertiary); }
.thinking-toggle .chevron-down.rotated { transform: rotate(180deg); }
.thinking-list { margin: 0; padding: 4px 12px 10px 26px; }
.thinking-list li { font-size: 12px; color: var(--text-tertiary); margin-bottom: 4px; line-height: 1.5; }
.think-action {
  display: inline-block;
  padding: 0 7px;
  margin-right: 6px;
  border-radius: var(--radius-pill);
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
}

.answer-loading { display: flex; gap: 5px; padding: 4px 0; }
.answer-loading .dot {
  width: 7px; height: 7px; border-radius: 50%; background: var(--text-tertiary);
  animation: blink 1.2s infinite ease-in-out;
}
.answer-loading .dot:nth-child(2) { animation-delay: 0.2s; }
.answer-loading .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.25; } 40% { opacity: 1; } }

.answer-error { margin-top: 10px; font-size: 12.5px; color: #DC2626; }

/* 引用文档 */
.refs-section { margin-top: 14px; }
.refs-label { font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-bottom: 10px; }
.refs-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.ref-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  transition: box-shadow var(--dur-fast), transform var(--dur-fast);
}
.ref-card:hover { box-shadow: var(--shadow-float); transform: translateY(-1px); }
.ref-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ref-icon.src-kb { background: #DBEAFE; color: #1E40AF; }
.ref-icon.src-web { background: #D1FAE5; color: #065F46; }
.ref-icon.src-graph { background: #FEF3C7; color: #92400E; }
.ref-info { min-width: 0; }
.ref-name { font-size: 12.5px; font-weight: 600; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ref-meta { display: flex; gap: 8px; font-size: 11px; color: var(--text-tertiary); margin: 2px 0 4px; }
.ref-kb { color: var(--brand); }
.ref-snippet {
  font-size: 11.5px;
  color: var(--text-tertiary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 引用文件卡片（原型风格） */
.ref-file-card {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; border-radius: var(--radius-md);
  background: var(--bg-surface); border: 1px solid var(--border);
  transition: all var(--dur-fast); cursor: default;
}
.ref-file-card:hover { border-color: var(--brand); box-shadow: 0 2px 8px rgba(59,130,246,.12); }
.rfc-icon {
  width: 38px; height: 38px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.rfc-icon.src-kb { background: #DBEAFE; color: #1E40AF; }
.rfc-icon.src-web { background: #D1FAE5; color: #065F46; }
.rfc-icon.src-graph { background: #FEF3C7; color: #92400E; }
.rfc-info { flex: 1; min-width: 0; }
.rfc-name { font-size: 13px; font-weight: 600; color: var(--brand); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rfc-meta-row {
  display: flex; gap: 12px; font-size: 11.5px; color: var(--text-tertiary); margin-top: 3px;
}

/* 反馈 */
.feedback-row { display: flex; gap: 6px; margin-top: 12px; }
.fb-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--dur-fast);
}
.fb-btn:hover { background: var(--bg-hover); }
.fb-btn.on { background: var(--brand-soft); border-color: var(--brand); color: var(--brand); }

/* ---- 建议追问 ---- */
.suggest-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px 8px;
  flex-wrap: wrap;
}
.suggest-label { font-size: 13px; font-weight: 600; color: var(--text-secondary); white-space: nowrap; }
.chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 13px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-surface);
  cursor: pointer;
  transition: all var(--dur-fast);
  white-space: nowrap;
  font-family: inherit;
}
.chip:hover { border-color: var(--brand); color: var(--brand); background: var(--brand-soft); }

/* ---- 输入区 ---- */
.input-area {
  padding: 12px 24px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-surface);
}
.attach-preview { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.attach-preview-item { position: relative; }
.attach-thumb { width: 48px; height: 48px; border-radius: 8px; object-fit: cover; border: 1px solid var(--border); }
.attach-remove {
  position: absolute;
  top: -5px;
  right: -5px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: none;
  background: #DC2626;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.chat-input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  font-size: 14px;
  resize: none;
  outline: none;
  font-family: inherit;
  line-height: 1.5;
  background: var(--bg-surface);
  color: var(--text-primary);
  transition: border-color var(--dur-fast), box-shadow var(--dur-fast);
}
.chat-input:focus { border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); }
.chat-input::placeholder { color: var(--text-placeholder); }

.input-bar { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }
.input-left { display: flex; align-items: center; gap: 10px; }
.attach-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  overflow: hidden;
  transition: all var(--dur-fast);
}
.attach-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.char-count { font-size: 12px; color: var(--text-tertiary); }
.input-actions { display: flex; align-items: center; gap: 8px; }
.send-btn { height: 36px; padding: 0 20px; font-size: 13px; }

@media (max-width: 720px) {
  .chat-sidebar { width: 200px; }
}

/* ---- 二级页（问答记录 / 模型配置）---- */
.secondary-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}
.records-card { padding: 0; overflow: hidden; }
.records-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.records-table th {
  text-align: left;
  padding: 12px 16px;
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 12px;
  border-bottom: 1px solid var(--border);
}
.records-table td { padding: 12px 16px; border-bottom: 1px solid var(--border); color: var(--text-primary); }
.records-table tr:last-child td { border-bottom: none; }
.col-name { font-weight: 600; }
.col-time { color: var(--text-tertiary); white-space: nowrap; }
.link-btn {
  border: none;
  background: transparent;
  color: var(--brand);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  padding: 0;
}
.link-btn:hover { text-decoration: underline; }
.empty-hint { padding: 24px; text-align: center; color: var(--text-tertiary); font-size: 13px; }

.model-card { padding: 20px; max-width: 560px; }
.model-note { margin: -6px 0 18px; font-size: 12.5px; color: var(--text-tertiary); line-height: 1.6; }
.model-field { margin-bottom: 18px; }
.model-field > label { display: block; font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.field-row { display: flex; align-items: center; gap: 12px; }
.field-val { font-size: 13px; font-weight: 600; color: var(--brand); min-width: 28px; }
.range { flex: 1; accent-color: var(--brand); }
.select {
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
}
.select:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); }
</style>
