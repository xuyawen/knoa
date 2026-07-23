<script setup lang="ts">
// 智能搜索 — 文档搜索结果页：左侧历史/热门，右侧结果列表 + 关键词高亮。
import { ref, computed, onMounted } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import { useToastStore } from '@/stores/toast'
import { searchDocs, getTrending } from '@/api'
import type { SearchDocItem, TrendingItem, Paginated } from '@/types/api'

const props = defineProps<{ section?: string }>()
const section = computed(() => props.section ?? 'history')

const toast = useToastStore()

// ── 搜索框 ──
const query = ref('')
const submitted = ref('')
const loading = ref(false)
const results = ref<Paginated<SearchDocItem> | null>(null)
const searchCost = ref<number | null>(null)

// ── 来源筛选（真实过滤，后端已支撑）──
const typeOpts = [
  { label: '全部类型', value: '' },
  { label: 'PDF', value: 'pdf' },
  { label: 'Word', value: 'docx' },
  { label: 'TXT', value: 'txt' },
  { label: 'MD', value: 'md' },
]
const scopeOpts = [
  { label: '全部权限', value: '' },
  { label: '公开', value: 'public' },
  { label: '公司内部', value: 'company' },
  { label: '部门', value: 'department' },
  { label: '私有', value: 'private' },
]
const statusOpts = [
  { label: '已审核', value: '已审核' },
  { label: '待复核', value: '待复核' },
  { label: '已拒绝', value: '已拒绝' },
]
const filterType = ref('')
const filterScope = ref('')
const filterStatus = ref('已审核')

// ── 本地搜索历史 ──
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

// ── 热门搜索 ──
const trending = ref<TrendingItem[]>([])
async function loadTrending() {
  try { trending.value = await getTrending() } catch { trending.value = [] }
}

// ── 执行搜索 ──
async function runSearch(page = 1) {
  const text = query.value.trim()
  if (!text || loading.value) return
  loading.value = true
  submitted.value = text
  const t0 = performance.now()
  try {
    results.value = await searchDocs(text, {
      page,
      size: 20,
      type: filterType.value,
      scope: filterScope.value,
      status: filterStatus.value,
    })
    saveHistory(text)
  } catch (e: any) {
    toast.error(`搜索失败：${e?.message || e}`)
    results.value = null
  } finally {
    loading.value = false
    searchCost.value = Math.round((performance.now() - t0) * 10) / 1000
  }
}

function pick(text: string) {
  query.value = text
  void runSearch()
}

function clearSearch() {
  query.value = ''
}

function resetFilters() {
  filterType.value = ''
  filterScope.value = ''
  filterStatus.value = '已审核'
}

// ── 关键词高亮 ──
const highlight = computed(() => {
  const q = submitted.value.trim()
  if (!q) return (text: string) => text
  const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`(${escaped})`, 'gi')
  return (text: string) => text.replace(re, '<mark>$1</mark>')
})

function fileIcon(type: string): string {
  switch (type.toUpperCase()) {
    case 'PDF': return 'file-text'
    case 'DOCX': return 'file-text'
    case 'XLSX': return 'table'
    case 'MD': return 'file-code'
    default: return 'file'
  }
}
function fileIconClass(type: string): string {
  const t = type.toUpperCase()
  if (t === 'PDF') return 'pdf'
  if (t === 'DOCX') return 'docx'
  if (t === 'XLSX') return 'xlsx'
  if (t === 'MD') return 'md'
  return 'txt'
}
function fmtTime(iso: string) {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? iso : d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
function scopeLabel(scope: string): string {
  const map: Record<string, string> = { public: '公开', company: '公司内部', department: '部门可见', private: '仅本人可见' }
  return map[scope] || scope
}
</script>

<template>
  <div class="search-page">
    <!-- 左侧边栏 -->
    <aside class="search-sidebar">
      <div class="nav-menu">
        <button class="nav-item" :class="{ active: section === 'history' }">
          <Icon name="clock" :size="16" />
          <span>搜索历史</span>
        </button>
        <button class="nav-item" :class="{ active: section === 'popular' }">
          <Icon name="fire" :size="16" />
          <span>热门搜索</span>
        </button>
      </div>

      <div class="side-section">
        <div class="side-head">
          <span class="side-title">搜索历史</span>
          <button v-if="searchHistory.length" class="side-clear" @click="clearHistory">清空</button>
        </div>
        <div v-if="searchHistory.length" class="side-list">
          <div
            v-for="h in searchHistory"
            :key="h"
            class="side-item"
            @click="pick(h)"
          >
            <Icon name="clock" :size="13" />
            <span class="side-txt">{{ h }}</span>
            <button class="side-del" title="移除" @click.stop="removeHistoryItem(h, $event)">
              <Icon name="close" :size="10" />
            </button>
          </div>
        </div>
        <div v-else class="side-empty">暂无搜索历史</div>
      </div>

      <div class="side-section">
        <div class="side-head">
          <span class="side-title">热门搜索</span>
        </div>
        <div v-if="trending.length" class="side-list">
          <div
            v-for="(t, i) in trending.slice(0, 8)"
            :key="t.question"
            class="side-item"
            @click="pick(t.question)"
          >
            <span class="side-rank" :class="'rk-' + Math.min(i + 1, 3)">{{ i + 1 }}</span>
            <span class="side-txt">{{ t.question }}</span>
          </div>
        </div>
        <div v-else class="side-empty">暂无热门数据</div>
      </div>
    </aside>

    <!-- 右侧主区域 -->
    <main class="search-main">
      <!-- 搜索栏 -->
      <div class="search-bar-row card">
        <div class="search-input-wrap">
          <Icon name="search" :size="17" class="sb-icon" />
          <input
            v-model="query"
            type="text"
            placeholder="企业数据安全管理规范"
            class="sb-input"
            @keydown.enter="runSearch()"
          />
          <button v-if="query" class="sb-clear" @click="clearSearch">
            <Icon name="close" :size="13" />
          </button>
        </div>
        <button
          class="btn btn-primary sb-btn"
          :disabled="!query.trim() || loading"
          @click="runSearch()"
        >
          {{ loading ? '检索中…' : '搜索' }}
        </button>
        <span class="adv-link">高级搜索 <Icon name="chevron-down" :size="11" /></span>
      </div>

      <!-- 结果区 -->
      <div v-if="submitted" class="result-area card">
        <div class="result-toolbar">
          <div class="filter-row">
            <CustomSelect v-model="filterType" :options="typeOpts" placeholder="文件类型" width="110px" />
            <CustomSelect v-model="filterScope" :options="scopeOpts" placeholder="权限范围" width="120px" />
            <CustomSelect v-model="filterStatus" :options="statusOpts" placeholder="文档状态" width="110px" />
            <button class="flink" @click="resetFilters">清空</button>
            <button class="btn btn-primary btn-sm" @click="runSearch(results?.page ?? 1)">应用筛选</button>
          </div>
          <div class="result-meta">
            找到约 <b>{{ results?.total ?? 0 }}</b> 条结果
            <span v-if="searchCost !== null">（用时 {{ searchCost.toFixed(3) }} 秒）</span>
          </div>
        </div>

        <div v-if="loading" class="result-loading">
          <span class="dot" /><span class="dot" /><span class="dot" />
        </div>

        <div v-else-if="results && results.items.length" class="doc-list">
          <div
            v-for="doc in results.items"
            :key="doc.id"
            class="doc-card"
          >
            <div class="doc-icon" :class="fileIconClass(doc.type)">
              <Icon :name="fileIcon(doc.type)" :size="20" />
            </div>
            <div class="doc-body">
              <div class="doc-title" v-html="highlight(doc.title)"></div>
              <div class="doc-snippet" v-html="highlight(doc.snippet || '暂无摘要')"></div>
              <div class="doc-meta">
                <span class="meta-item">
                  <Icon name="folder" :size="12" />
                  来自：{{ doc.kbName }}{{ doc.category ? ` > ${doc.category}` : '' }}
                </span>
                <span class="meta-item">
                  <Icon name="clock" :size="12" />
                  更新时间：{{ fmtTime(doc.updatedAt) }}
                </span>
                <span class="meta-item">
                  <Icon name="shield" :size="12" />
                  权限：{{ scopeLabel(doc.scope) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="results" class="empty-hint">未找到与「{{ submitted }}」相关的文档</div>
      </div>

      <!-- 空状态提示 -->
      <div v-else class="welcome card">
        <Icon name="search" :size="40" class="welcome-icon" />
        <div class="welcome-title">输入关键词，搜索知识库文档</div>
        <div class="welcome-desc">支持按文件类型、权限范围、审核状态筛选</div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.search-page {
  display: flex;
  gap: 16px;
  height: 100%;
  min-height: 0;
}

/* ---- 左侧边栏 ---- */
.search-sidebar {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  font-size: 13.5px;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  font-family: inherit;
  transition: all var(--dur-fast);
}
.nav-item:hover { background: var(--bg-hover); color: var(--text-primary); }
.nav-item.active { background: var(--brand-soft); color: var(--brand); font-weight: 600; }

.side-section {
  padding: 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}
.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.side-title { font-size: 13px; font-weight: 700; color: var(--text-primary); }
.side-clear {
  font-size: 12px;
  color: var(--text-tertiary);
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
}
.side-clear:hover { color: var(--danger); }
.side-list { display: flex; flex-direction: column; gap: 2px; }
.side-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: var(--radius-md);
  font-size: 12.5px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--dur-fast);
}
.side-item:hover { background: var(--bg-hover); color: var(--text-primary); }
.side-txt { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.side-rank {
  width: 18px; height: 18px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 5px;
  font-size: 11px; font-weight: 700;
  background: var(--bg-subtle); color: var(--text-secondary);
}
.side-rank.rk-1 { background: var(--brand); color: var(--text-on-brand); }
.side-rank.rk-2 { background: var(--brand-soft); color: var(--brand); }
.side-rank.rk-3 { background: var(--warning-soft); color: var(--warning); }
.side-del {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%;
  color: var(--text-tertiary); opacity: 0;
  transition: all var(--dur-fast);
}
.side-item:hover .side-del { opacity: 1; }
.side-del:hover { background: var(--bg-hover); color: var(--danger); }
.side-empty { font-size: 12.5px; color: var(--text-tertiary); padding: 8px 0; }

/* ---- 右侧主区域 ---- */
.search-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

/* 搜索栏 */
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

/* 结果区 */
.result-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px 18px;
  min-height: 300px;
}
.result-toolbar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 14px;
}
.filter-row {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.btn-sm {
  height: 32px;
  padding: 0 14px;
  font-size: 12.5px;
}
.flink {
  font-size: 12.5px; color: var(--brand); background: none; border: none;
  cursor: pointer; font-family: inherit; padding: 0;
}
.result-meta {
  font-size: 13px; color: var(--text-secondary);
}
.result-meta b { color: var(--text-primary); }

.result-loading {
  display: flex; gap: 5px; padding: 24px 0; justify-content: center;
}
.result-loading .dot {
  width: 7px; height: 7px; border-radius: 50%; background: var(--text-tertiary);
  animation: blink 1.2s infinite ease-in-out;
}
.result-loading .dot:nth-child(2) { animation-delay: 0.2s; }
.result-loading .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.25; } 40% { opacity: 1; } }

/* 文档列表 */
.doc-list { display: flex; flex-direction: column; gap: 14px; }
.doc-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 0;
  border-bottom: 1px solid var(--border);
}
.doc-card:last-child { border-bottom: none; padding-bottom: 0; }
.doc-icon {
  width: 44px; height: 44px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  background: var(--bg-subtle);
  color: var(--text-secondary);
}
.doc-icon.pdf { background: #fff0f0; color: #d93025; }
.doc-icon.docx { background: #e8f0fe; color: #1a73e8; }
.doc-icon.xlsx { background: #e6f4ea; color: #137333; }
.doc-icon.md { background: var(--bg-subtle); color: var(--text-secondary); }
.doc-icon.txt { background: var(--bg-subtle); color: var(--text-secondary); }
.doc-body { flex: 1; min-width: 0; }
.doc-title {
  font-size: 14.5px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 6px;
  line-height: 1.4;
}
.doc-title :deep(mark) {
  background: #fff3b0;
  color: #b45f06;
  padding: 0 2px;
  border-radius: 2px;
}
.doc-snippet {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.doc-snippet :deep(mark) {
  background: #fff3b0;
  color: #b45f06;
  padding: 0 2px;
  border-radius: 2px;
}
.doc-meta {
  display: flex; align-items: center; flex-wrap: wrap;
  gap: 14px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.meta-item { display: inline-flex; align-items: center; gap: 4px; }

.empty-hint {
  padding: 40px 0;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
}

/* 欢迎态 */
.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 300px;
}
.welcome-icon { color: var(--brand-soft); }
.welcome-title { font-size: 15px; font-weight: 700; color: var(--text-primary); }
.welcome-desc { font-size: 13px; color: var(--text-secondary); }
</style>
