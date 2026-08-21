<script setup lang="ts">
// 智能搜索主页：搜索框 + 筛选条 + 文档结果列表（带关键词高亮）。
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Icon from '@/components/ui/Icon.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { searchDocs, getDocumentById } from '@/api'
import type { SearchDocItem, Paginated, DocumentDetail } from '@/types/api'
import { useSearchHistory } from '@/composables/useSearchHistory'
import { useDebouncedWatch } from '@/composables/useDebouncedWatch'

const route = useRoute()
const toast = useToastStore()
const { save: saveHistory } = useSearchHistory()

// ── 搜索框 ──
const query = ref('')
const submitted = ref('')
const loading = ref(false)
const results = ref<Paginated<SearchDocItem> | null>(null)
const searchCost = ref<number | null>(null)

// ── 来源筛选 ──
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
  { label: '部门', value: 'department' },
  { label: '私有', value: 'private' },
]
const statusOpts = [
  { label: '已审核', value: '已审核' },
  { label: '待复核', value: '待复核' },
  { label: '已拒绝', value: '已拒绝' },
]
const timeOpts = [
  { label: '不限时间', value: '' },
  { label: '近7天', value: '7d' },
  { label: '近30天', value: '30d' },
  { label: '近3个月', value: '90d' },
  { label: '近半年', value: '180d' },
]
const filterType = ref('')
const filterScope = ref('')
const filterStatus = ref('已审核')
const filterTime = ref('')

onMounted(() => {
  const q = (route.query.q as string) || ''
  if (q) {
    query.value = q
    cancelSearchDebounce() // 赋值会触发防抖 watcher，撤销它避免 300ms 后重复检索
    void runSearch()
  }
})

// 输入即搜索：停顿 400ms 才发起（混合检索较重，比标准防抖略长）。
// 停顿瞬间恰有检索在途时记下意图，待其结束自动补搜，避免结果落后于输入。
let searchAgain = false
const { cancel: cancelSearchDebounce } = useDebouncedWatch(
  query,
  () => {
    if (loading.value) {
      searchAgain = true
      return
    }
    void runSearch()
  },
  400,
)
watch(loading, (v) => {
  if (!v && searchAgain) {
    searchAgain = false
    void runSearch()
  }
})

// 回车：立即检索，并撤销待发的防抖搜索
function submitSearch() {
  cancelSearchDebounce()
  searchAgain = false
  void runSearch()
}

// 筛选条件变化：对已提交关键词立即重搜（与「输入即搜索」交互一致）
watch([filterType, filterScope, filterStatus, filterTime], () => {
  if (submitted.value) void runSearch()
})

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
      time: filterTime.value,
    })
    saveHistory(text)
  } catch (e: unknown) {
    toast.error(`搜索失败：${errMsg(e)}`)
    results.value = null
  } finally {
    loading.value = false
    searchCost.value = Math.round((performance.now() - t0) * 10) / 1000
  }
}

function clearSearch() {
  query.value = ''
}

function resetFilters() {
  filterType.value = ''
  filterScope.value = ''
  filterStatus.value = '已审核'
  filterTime.value = ''
}

// ── 关键词高亮 ──
// 先转义 HTML 特殊字符再注入 <mark>，避免后端真实文档标题/摘要里的
// <script>/<img onerror> 等被 v-html 执行（XSS 防护）。
const escapeHtml = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
const highlight = computed(() => {
  const q = submitted.value.trim()
  if (!q) return (text: string) => escapeHtml(text)
  const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`(${escaped})`, 'gi')
  return (text: string) => escapeHtml(text).replace(re, '<mark>$1</mark>')
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
  const map: Record<string, string> = { public: '公开', department: '部门可见', private: '本人可见' }
  return map[scope] || scope
}

// ── 源文档预览（点击搜索结果直接查看原文）──
const showPreview = ref(false)
const previewDoc = ref<DocumentDetail | null>(null)
const previewLoading = ref(false)

async function openPreview(docId: string) {
  showPreview.value = false
  previewDoc.value = null
  previewLoading.value = true
  try {
    previewDoc.value = await getDocumentById(docId)
    showPreview.value = true
  } catch (e: unknown) {
    toast.error(`加载文档失败：${errMsg(e)}`)
  } finally {
    previewLoading.value = false
  }
}
function closePreview() {
  showPreview.value = false
  previewDoc.value = null
}
</script>

<template>
  <div class="search-page">
    <!-- 搜索栏（搜索框一行，筛选条件下一行；输入即搜索，回车立即检索） -->
    <div class="search-bar card">
      <div class="search-input-row">
        <div class="search-input-wrap">
          <Icon name="search" :size="17" class="sb-icon" />
          <input
            v-model="query"
            type="text"
            placeholder="企业数据安全管理规范"
            class="sb-input"
            @keydown.enter="submitSearch"
          />
          <button v-if="query" class="sb-clear" @click="clearSearch">
            <Icon name="close" :size="13" />
          </button>
        </div>
      </div>
      <div class="filter-row">
        <CustomSelect v-model="filterType" :options="typeOpts" placeholder="文件类型" width="110px" />
        <CustomSelect v-model="filterScope" :options="scopeOpts" placeholder="权限范围" width="120px" />
        <CustomSelect v-model="filterStatus" :options="statusOpts" placeholder="文档状态" width="110px" />
        <CustomSelect v-model="filterTime" :options="timeOpts" placeholder="更新时间" width="110px" />
        <button class="btn btn-ghost btn-sm" @click="resetFilters">重置</button>
      </div>
    </div>

    <!-- 结果区 -->
    <div v-if="submitted" class="result-area card">
      <div class="result-toolbar">
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
          @click="openPreview(doc.id)"
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

      <EmptyState v-else-if="results" />
    </div>

    <!-- 未搜索时的欢迎态 -->
    <div v-else class="welcome card">
      <Icon name="search" :size="40" class="welcome-icon" />
      <div class="welcome-title">输入关键词，搜索知识库文档</div>
      <div class="welcome-desc">支持按文件类型、权限范围、审核状态筛选</div>
    </div>

    <!-- 源文档预览弹窗 -->
    <AppModal :show="showPreview || previewLoading" :title="previewDoc?.title || '文档预览'" wide @close="closePreview">
      <div v-if="previewLoading" class="modal-hint">加载中…</div>
      <template v-else-if="previewDoc">
        <div class="preview-meta">
          <span class="type-text">{{ previewDoc.type }}</span>
          <span class="meta-time">{{ fmtTime(previewDoc.updatedAt) }}</span>
          <span v-if="previewDoc.originalFilename" class="doc-file-name">{{ previewDoc.originalFilename }}</span>
        </div>
        <pre class="preview-body">{{ previewDoc.contentMd || '（无内容）' }}</pre>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.search-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  min-height: 0;
}

/* 搜索栏（搜索框+按钮一行，筛选下一行） */
.search-bar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
}
.search-input-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.search-input-wrap {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
}
.sb-icon {
  position: absolute;
  left: 12px;
  color: var(--text-tertiary);
  pointer-events: none;
}
.sb-input {
  width: 100%;
  height: 32px;
  padding: 0 34px 0 38px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
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
  width: 20px;
  height: 20px;
  border-radius: 50%;
  color: var(--text-tertiary);
  cursor: pointer;
  background: transparent;
  border: none;
}
.sb-clear:hover { background: var(--bg-hover); }

/* 筛选条件行（搜索框下方） */
.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* 结果区 */
.result-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  min-height: 300px;
}
.result-toolbar {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 14px;
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
  cursor: pointer;
}
.doc-card:last-child { border-bottom: none; padding-bottom: 0; }
.doc-icon {
  width: 44px; height: 44px;
  border-radius: var(--radius-md);
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

/* 源文档预览 */
.modal-hint { padding: 40px 0; text-align: center; color: var(--text-tertiary); font-size: 13px; }
.preview-meta {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding-bottom: 12px; margin-bottom: 14px; border-bottom: 1px solid var(--border);
}
.type-text { font-size: 12px; font-weight: 600; color: var(--text-secondary); background: var(--bg-subtle); padding: 2px 10px; border-radius: var(--radius-sm); }
.meta-time { font-size: 12px; color: var(--text-tertiary); }
.doc-file-name { font-size: 12px; color: var(--text-tertiary); }
.preview-body {
  margin: 0; padding: 14px 16px; background: var(--bg-subtle); border-radius: var(--radius-md);
  font-size: 13px; line-height: 1.75; color: var(--text-primary); white-space: pre-wrap; word-break: break-word;
  max-height: 52vh; overflow-y: auto;
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
/* 亮色用品牌蓝加深；暗色下品牌蓝叠透明度会发暗，改用固定浅蓝保证可见性 */
.welcome-icon { color: var(--brand); opacity: 0.45; }
[data-theme='dark'] .welcome-icon { color: #60A5FA; opacity: 0.8; }
.welcome-title { font-size: 15px; font-weight: 700; color: var(--text-primary); }
.welcome-desc { font-size: 13px; color: var(--text-secondary); }
</style>
