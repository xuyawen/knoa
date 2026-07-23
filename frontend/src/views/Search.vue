<script setup lang="ts">
// 智能搜索 — 搜索即问答：复用 /api/ask 流式接口，
// 把输入当作问题直接检索，结果以「AI 答案 + 溯源卡片」呈现。
// 去掉了原 mock 中无后端支撑的假筛选下拉与假统计数。
// section 由路由决定（history/popular/filters）。
import { ref, computed, nextTick, onMounted } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import { useToastStore } from '@/stores/toast'
import { streamAsk, getTrending } from '@/api'
import type { ThinkingStep, SourceItem, TrendingItem } from '@/types/api'

const props = defineProps<{ section?: string }>()
const section = computed(() => props.section ?? 'history')

// 热门搜索（真实 trending 数据）
const trending = ref<TrendingItem[]>([])
async function loadTrending() {
  try {
    trending.value = await getTrending()
  } catch {
    trending.value = []
  }
}

const toast = useToastStore()

const query = ref('')
const submitted = ref('')        // 当前已提交的问题
const answer = ref('')           // 流式累积的回答正文
const sources = ref<SourceItem[]>([])
const thinking = ref<ThinkingStep[]>([])
const streaming = ref(false)
const errorMsg = ref('')
const showThinking = ref(false)
const askAbort = ref<AbortController | null>(null)
const scrollRef = ref<HTMLElement | null>(null)
const searchCost = ref<number | null>(null)

const suggested = [
  '数据安全分级分类标准是怎样的？',
  '员工入职需要准备哪些材料？',
  '差旅报销流程是什么？',
  '如何申请系统权限？',
]

// ── 来源筛选（按 SourceItem.sourceType 前端过滤，后端暂无时间/分类/权限元数据）
const sourceOptions = [
  { label: '知识库', value: 'kb' },
  { label: '联网搜索', value: 'web' },
  { label: '知识图谱', value: 'graph' },
]
const sourceSel = ref<Set<string>>(new Set(['kb']))
function toggleSource(o: string) {
  const next = new Set(sourceSel.value)
  if (next.has(o)) next.delete(o)
  else next.add(o)
  sourceSel.value = next
}
const filteredSources = computed(() => {
  if (!sources.value.length || sourceSel.value.size === 0) return sources.value
  if (sourceSel.value.size === sourceOptions.length) return sources.value
  return sources.value.filter((s) => s.sourceType && sourceSel.value.has(s.sourceType))
})
function resetSources() {
  sourceSel.value = new Set(['kb'])
}

// ── 本地搜索历史
const HISTORY_KEY = 'knoa_search_history'
const MAX_HISTORY = 20
const searchHistory = ref<string[]>([])
onMounted(() => {
  loadHistory()
  void loadTrending()
})
function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    searchHistory.value = raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    searchHistory.value = []
  }
}
function saveHistory(text: string) {
  if (!text.trim()) return
  const next = [text, ...searchHistory.value.filter((h) => h !== text)].slice(0, MAX_HISTORY)
  searchHistory.value = next
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(next)) } catch { /* ignore */ }
}
function clearHistory() {
  searchHistory.value = []
  try { localStorage.removeItem(HISTORY_KEY) } catch { /* ignore */ }
}
function removeHistoryItem(text: string, e: Event) {
  e.stopPropagation()
  const next = searchHistory.value.filter((h) => h !== text)
  searchHistory.value = next
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(next)) } catch { /* ignore */ }
}

function scrollToBottom() {
  nextTick(() => {
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function runSearch() {
  const text = query.value.trim()
  if (!text || streaming.value) return
  const t0 = performance.now()
  submitted.value = text
  answer.value = ''
  sources.value = []
  thinking.value = []
  errorMsg.value = ''
  showThinking.value = false
  streaming.value = true

  const ac = new AbortController()
  askAbort.value = ac
  try {
    // 纯搜索场景：不挂 sessionId，走全局检索；事件结构与 Chat 完全一致。
    // 传 mode='search' 让后端埋点区分「搜索」与「问答」，Dashboard 才能分别统计。
    for await (const ev of streamAsk(text, null, null, undefined, { signal: ac.signal, mode: 'search' })) {
      if (ev.event === 'thinking') {
        thinking.value = [...thinking.value, ev.data as ThinkingStep]
      } else if (ev.event === 'sources') {
        sources.value = ev.data as SourceItem[]
      } else if (ev.event === 'delta') {
        answer.value += (ev.data as { content: string }).content
        scrollToBottom()
      } else if (ev.event === 'error') {
        errorMsg.value = (ev.data as { message: string }).message
        toast.error(`搜索出错：${errorMsg.value}`)
      }
      // 'done' / 'message' 在搜索场景无需持久化，忽略
    }
  } catch (e: any) {
    if (e?.name !== 'AbortError') {
      toast.error(`搜索中断：${e?.message || e}`)
    }
  } finally {
    streaming.value = false
    askAbort.value = null
    searchCost.value = Math.round((performance.now() - t0) * 100) / 100
    if (!errorMsg.value && submitted.value) saveHistory(submitted.value)
  }
}

function stop() {
  askAbort.value?.abort()
}

function resetSearch() {
  submitted.value = ''
  answer.value = ''
  sources.value = []
  thinking.value = []
  errorMsg.value = ''
}

function pick(s: string) {
  query.value = s
  runSearch()
}

function clearSearch() {
  query.value = ''
}
</script>

<template>
  <div class="search-page">
    <!-- ====== 热门搜索（真实 trending）====== -->
    <template v-if="section === 'popular'">
      <div class="card popular-card">
        <div class="panel-head">
          <span class="panel-title">热门搜索榜</span>
          <Icon name="fire" :size="14" class="info-hint" />
        </div>
        <ul v-if="trending.length" class="popular-list">
          <li v-for="(t, i) in trending" :key="t.question">
            <span class="rank" :class="'rk-' + Math.min(i + 1, 3)">{{ i + 1 }}</span>
            <span class="q">{{ t.question }}</span>
            <span class="cnt">{{ t.count }}</span>
          </li>
        </ul>
        <div v-else class="empty-hint">暂无热门搜索数据</div>
      </div>
    </template>

    <!-- ====== 搜索筛选（来源类型会实际过滤结果）====== -->
    <template v-else-if="section === 'filters'">
      <div class="card filter-card">
        <div class="panel-head">
          <span class="panel-title">搜索筛选</span>
          <Icon name="filter" :size="14" class="info-hint" />
        </div>
        <p class="filter-desc">配置检索来源类型，搜索结果会按选中类型过滤。</p>
        <div class="filter-group">
          <div class="filter-label">来源类型</div>
          <div class="filter-toggles">
            <button
              v-for="opt in sourceOptions"
              :key="opt.value"
              class="filter-toggle"
              :class="{ on: sourceSel.has(opt.value) }"
              @click="toggleSource(opt.value)"
            >{{ opt.label }}</button>
          </div>
        </div>
        <div class="filter-hint">提示：默认只检索知识库。勾选「联网搜索」可在无命中时自动补充网络结果（若管理员已开启联网能力）。</div>
      </div>
    </template>

    <!-- ====== 搜索历史 / 默认：搜索即问答 ====== -->
    <template v-else>
    <div class="search-bar-row card">
      <div class="search-input-wrap">
        <Icon name="search" :size="17" class="sb-icon" />
        <input
          v-model="query"
          type="text"
          placeholder="企业数据安全管理规范"
          class="sb-input"
          @keydown.enter="runSearch"
        />
        <button v-if="query" class="sb-clear" @click="clearSearch">
          <Icon name="close" :size="13" />
        </button>
      </div>
      <button
        class="btn btn-primary sb-btn"
        :disabled="!query.trim() || streaming"
        @click="runSearch"
      >
        {{ streaming ? '检索中…' : '搜索' }}
      </button>
      <span class="adv-link">高级搜索 <Icon name="chevron-down" :size="11" /></span>
    </div>

    <!-- 空状态：最近搜索 + 热门搜索建议 -->
    <template v-if="!submitted">
      <div v-if="searchHistory.length" class="history-row">
        <div class="history-head">
          <span class="history-title">最近搜索</span>
          <button class="history-clear" @click="clearHistory">清空</button>
        </div>
        <div class="history-list">
          <button
            v-for="h in searchHistory"
            :key="h"
            class="history-chip"
            @click="pick(h)"
          >
            <Icon name="clock" :size="13" />
            <span class="history-txt">{{ h }}</span>
            <span class="history-del" title="移除" @click="removeHistoryItem(h, $event)"><Icon name="close" :size="11" /></span>
          </button>
        </div>
      </div>
      <div class="suggest-row">
        <span class="suggest-label">大家都在搜</span>
        <button v-for="(s, i) in suggested" :key="i" class="chip" @click="pick(s)">{{ s }}</button>
      </div>
    </template>

    <!-- ====== 结果区 ====== -->
    <div v-else class="result-area" ref="scrollRef">
      <!-- 筛选行 + 结果计数 -->
      <div class="result-toolbar">
        <div class="filter-row">
          <span class="filter-label-inline">来源</span>
          <button
            v-for="opt in sourceOptions"
            :key="opt.value"
            class="filter-toggle"
            :class="{ on: sourceSel.has(opt.value) }"
            @click="toggleSource(opt.value)"
          >{{ opt.label }}</button>
          <button class="flink" @click="resetSources">重置</button>
        </div>
        <div class="result-meta">
          <span>找到 <b>{{ filteredSources.length }}</b> 条结果<span v-if="searchCost !== null">（用时 {{ searchCost.toFixed(2) }} 秒）</span></span>
        </div>
      </div>
      <!-- 问题头 -->
      <div class="result-head">
        <h3 class="result-q">{{ submitted }}</h3>
        <button class="btn-ghost-sm" @click="resetSearch">新搜索</button>
      </div>

      <!-- 思考过程（折叠） -->
      <div v-if="thinking.length" class="thinking">
        <button class="thinking-toggle" @click="showThinking = !showThinking">
          <Icon name="sparkles" :size="13" />
          AI 检索过程（{{ thinking.length }} 步）
          <Icon name="chevron-down" :size="11" :class="{ rotated: showThinking }" />
        </button>
        <ul v-if="showThinking" class="thinking-list">
          <li v-for="t in thinking" :key="t.step">
            <span class="think-action">{{ t.action }}</span>
            <span class="think-detail">{{ t.detail }}</span>
          </li>
        </ul>
      </div>

      <!-- 回答正文 -->
      <div class="answer-card card">
        <div v-if="answer" class="answer-body">{{ answer }}</div>
        <div v-else-if="streaming" class="answer-loading">
          <span class="dot" /><span class="dot" /><span class="dot" />
        </div>
        <div v-else-if="errorMsg" class="answer-error">{{ errorMsg }}</div>
      </div>

      <!-- 来源卡片（溯源） -->
      <div v-if="filteredSources.length" class="refs-section">
        <div class="refs-label">为你检索到 {{ filteredSources.length }} 个相关来源</div>
        <div class="refs-list">
          <div v-for="(s, i) in filteredSources" :key="s.id ?? i" class="ref-card card">
            <div class="ref-icon" :class="`src-${s.sourceType || 'kb'}`">
              <Icon
                :name="s.sourceType === 'web' ? 'globe' : s.sourceType === 'graph' ? 'node' : 'doc'"
                :size="16"
              />
            </div>
            <div class="ref-info">
              <div class="ref-name">{{ s.title }}</div>
              <div class="ref-meta">
                <span class="ref-kb">{{ s.kb }}</span>
                <span v-if="s.confidence" class="ref-conf">相关度 {{ Math.round(s.confidence * 100) }}%</span>
              </div>
              <div class="ref-snippet">{{ s.snippet }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 停止 / 重新搜索 -->
      <div class="result-actions">
        <button v-if="streaming" class="btn btn-ghost" @click="stop">
          <Icon name="close" :size="14" /> 停止
        </button>
        <button v-else class="btn btn-ghost" @click="runSearch">
          <Icon name="refresh" :size="14" /> 重新搜索
        </button>
      </div>
    </div>
    </template>
  </div>
</template>

<style scoped>
.search-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
/* ---- 搜索栏 ---- */
.search-bar-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
}
.search-input-wrap {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
}
.sb-icon {
  position: absolute;
  left: 14px;
  color: var(--text-tertiary);
  pointer-events: none;
}
.sb-input {
  width: 100%;
  height: 42px;
  padding: 0 38px 0 40px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 14px;
  transition: all var(--dur-fast);
}
.sb-input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.sb-clear {
  position: absolute;
  right: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  color: var(--text-tertiary);
  cursor: pointer;
  background: transparent;
  border: none;
}
.sb-clear:hover { background: var(--bg-hover); }
.sb-btn { height: 42px; padding: 0 28px; font-size: 14px; }
.adv-link {
  display: inline-flex; align-items: center; gap: 3px;
  margin-left: auto; font-size: 12.5px; color: var(--brand);
  cursor: pointer; white-space: nowrap;
}

/* ---- 结果工具栏（筛选 + 计数） ---- */
.result-toolbar { display: flex; flex-direction: column; gap: 10px; }
.filter-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 10px 14px; border-radius: var(--radius-md);
  background: var(--bg-subtle); border: 1px solid var(--border);
}
.flink {
  font-size: 12.5px; color: var(--brand); background: none; border: none;
  cursor: pointer; font-family: inherit; padding: 0;
}
.result-meta {
  display: flex; align-items: center; gap: 16px;
  font-size: 13px; color: var(--text-secondary);
}
.result-meta b { color: var(--text-primary); }

/* ---- 建议 ---- */
.suggest-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 4px 0;
}
.suggest-label { font-size: 13px; font-weight: 600; color: var(--text-secondary); white-space: nowrap; }
.chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  font-size: 12.5px;
  color: var(--text-primary);
  background: var(--bg-surface);
  cursor: pointer;
  transition: all var(--dur-fast);
  white-space: nowrap;
  font-family: inherit;
}
.chip:hover { border-color: var(--brand); color: var(--brand); background: var(--brand-soft); }

/* ---- 搜索历史 ---- */
.history-row { display: flex; flex-direction: column; gap: 10px; }
.history-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
}
.history-title { font-size: 13px; font-weight: 600; color: var(--text-secondary); }
.history-clear {
  font-size: 12.5px; color: var(--text-tertiary); background: none; border: none;
  cursor: pointer; font-family: inherit;
}
.history-clear:hover { color: var(--danger); }
.history-list { display: flex; flex-wrap: wrap; gap: 8px; }
.history-chip {
  display: inline-flex; align-items: center; gap: 6px;
  max-width: 280px;
  padding: 6px 6px 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 12.5px;
  cursor: pointer;
  transition: all var(--dur-fast);
  font-family: inherit;
}
.history-chip:hover { border-color: var(--brand); color: var(--brand); background: var(--brand-soft); }
.history-txt { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-del {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%;
  color: var(--text-tertiary); flex-shrink: 0;
}
.history-chip:hover .history-del { color: var(--text-secondary); }
.history-del:hover { background: var(--bg-hover); color: var(--danger); }

/* 结果区筛选 */
.filter-label-inline {
  font-size: 12.5px; font-weight: 600; color: var(--text-secondary); margin-right: 2px;
}

/* ---- 结果区 ---- */
.result-area {
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
  padding-right: 2px;
}
.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.result-q {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.4;
}
.btn-ghost-sm {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  font-size: 12.5px;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  transition: all var(--dur-fast);
}
.btn-ghost-sm:hover { background: var(--bg-hover); color: var(--text-primary); }

/* 思考过程 */
.thinking {
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
  padding: 9px 12px;
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

/* 回答正文 */
.answer-card {
  padding: 18px 20px;
}
.answer-body {
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
.answer-loading { display: flex; gap: 5px; padding: 4px 0; }
.answer-loading .dot {
  width: 7px; height: 7px; border-radius: 50%; background: var(--text-tertiary);
  animation: blink 1.2s infinite ease-in-out;
}
.answer-loading .dot:nth-child(2) { animation-delay: 0.2s; }
.answer-loading .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.25; } 40% { opacity: 1; } }
.answer-error { font-size: 12.5px; color: var(--danger); }

/* 来源卡片（溯源） */
.refs-section { margin-top: 2px; }
.refs-label { font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-bottom: 10px; }
.refs-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }
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
.ref-icon.src-kb { background: var(--accent-blue-soft); color: var(--accent-blue); }
.ref-icon.src-web { background: var(--accent-green-soft); color: var(--accent-green); }
.ref-icon.src-graph { background: var(--accent-amber-soft); color: var(--accent-amber); }
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

/* 操作 */
.result-actions { display: flex; gap: 8px; }
.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 34px;
  padding: 0 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  font-size: 12.5px;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  transition: all var(--dur-fast);
}
.btn-ghost:hover { background: var(--bg-hover); color: var(--text-primary); }

/* 热门搜索榜 */
.popular-card { padding: 20px; }
.popular-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.popular-list li {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  transition: background var(--dur-fast);
}
.popular-list li:hover { background: var(--bg-hover); }
.rank {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border-radius: 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  background: var(--bg-surface);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}
.rank.rk-1 { background: var(--brand); color: var(--text-on-brand); }
.rank.rk-2 { background: var(--brand-soft); color: var(--brand); }
.rank.rk-3 { background: var(--warning-soft); color: var(--warning); }
.q { flex: 1; font-size: 13.5px; color: var(--text-primary); }
.cnt { font-size: 12px; font-weight: 600; color: var(--brand); background: var(--brand-soft); padding: 2px 9px; border-radius: var(--radius-pill); }

/* 搜索筛选 */
.filter-card { padding: 20px; max-width: 640px; }
.filter-desc { margin: 0 0 18px; font-size: 13px; color: var(--text-secondary); line-height: 1.6; }
.filter-group { margin-bottom: 18px; }
.filter-label { font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 10px; }
.filter-toggles { display: flex; flex-wrap: wrap; gap: 8px; }
.filter-toggle {
  padding: 7px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  transition: all var(--dur-fast);
}
.filter-toggle:hover { border-color: var(--brand); color: var(--brand); }
.filter-toggle.on { background: var(--brand); color: var(--text-on-brand); border-color: var(--brand); }
</style>
