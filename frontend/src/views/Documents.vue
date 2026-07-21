<script setup lang="ts">
// 文档管理 — 按 640(3).png 截图 1:1 还原，接真实文档生命周期。
// section 由路由决定（mine/public/department/archive）。
import { ref, computed, onMounted, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'
import {
  getDocuments,
  uploadDocument,
  approveDocument,
  rejectDocument,
  deleteDocument,
  aiReviewDocument,
  getDocument,
} from '@/api'
import type { DocumentItem, DocumentDetail, AIReview } from '@/types/api'

const knowledge = useKnowledgeStore()
const toast = useToastStore()
const auth = useAuthStore()

const props = defineProps<{ section?: string }>()
const section = computed(() => props.section ?? 'mine')

// 归档分类：后端未区分 owner/公开/部门维度，这里按状态映射「归档」；
// 其余分类（我的/公共/部门）暂共享同一文档列表，并用横幅说明后端待接入。
const scopedDocs = computed(() => {
  if (section.value === 'archive') return docs.value.filter((d) => d.status === '已拒绝')
  return docs.value
})

const selectedKb = ref<string>('')
const docs = ref<DocumentItem[]>([])
const loading = ref(false)
const uploading = ref(false)
const deleting = ref(false)

const searchQuery = ref('')
const viewMode = ref<'list' | 'grid'>('list')

// 筛选
const filterType = ref<string>('')
const filterStatus = ref<string>('')
const filterScope = ref<string>('')
const typeOptions = [
  { label: '全部类型', value: '' },
  { label: 'PDF', value: 'PDF' },
  { label: 'Word', value: 'DOCX' },
  { label: 'Excel', value: 'XLSX' },
  { label: 'PPT', value: 'PPTX' },
  { label: 'Markdown', value: 'MD' },
]
const statusOptions = [
  { label: '全部状态', value: '' },
  { label: '解析完成', value: '已审核' },
  { label: '解析中', value: '待复核' },
  { label: '解析失败', value: '已拒绝' },
]
const scopeOptions = [
  { label: '全部权限', value: '' },
  { label: '仅本人可见', value: 'self' },
  { label: '部门可见', value: 'dept' },
  { label: '公司可见', value: 'company' },
  { label: '公开可见', value: 'public' },
]

// 选择（批量删）
const selectedIds = ref<string[]>([])
// 分页
const currentPage = ref(1)
const pageSize = ref(10)

// 弹窗
const previewDoc = ref<DocumentDetail | null>(null)
const previewLoading = ref(false)
const aiReview = ref<AIReview | null>(null)
const aiReviewLoading = ref(false)

/* ---------- 数据加载 ---------- */
async function loadDocs() {
  if (!selectedKb.value) {
    docs.value = []
    return
  }
  loading.value = true
  selectedIds.value = []
  try {
    docs.value = await getDocuments(selectedKb.value)
  } catch (e: any) {
    docs.value = []
    toast.error(`加载文档失败：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!knowledge.loaded) await knowledge.load()
  if (knowledge.bases.length) {
    selectedKb.value = knowledge.bases[0].id
    await loadDocs()
  }
})

watch(selectedKb, async () => {
  currentPage.value = 1
  selectedIds.value = []
  await loadDocs()
})

/* ---------- 过滤 + 分页 ---------- */
const filteredDocs = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const base = scopedDocs.value
  if (!q) return base
  return base.filter((d) => d.title.toLowerCase().includes(q))
})

const totalPages = computed(() =>
  Math.max(1, Math.ceil(filteredDocs.value.length / pageSize.value)),
)

const pagedDocs = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredDocs.value.slice(start, start + pageSize.value)
})

watch([filteredDocs, pageSize], () => {
  if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
})

function clearSearch() {
  searchQuery.value = ''
}

/* ---------- 工具 ---------- */
function statusType(s: string): 'success' | 'warning' | 'danger' {
  if (s === '已审核') return 'success'
  if (s === '待复核' || s === '解析中') return 'warning'
  return 'danger'
}

function statusLabel(s: string): string {
  if (s === '已审核') return '解析完成'
  if (s === '待复核') return '解析中'
  if (s === '已拒绝') return '解析失败'
  return s
}

function fileMeta(type: string): { icon: string; color: string } {
  const t = (type || '').toUpperCase()
  if (t.includes('PDF')) return { icon: 'pdf', color: '#EF4444' }
  if (t.includes('DOC')) return { icon: 'doc', color: '#3B82F6' }
  if (t.includes('XLS')) return { icon: 'excel', color: '#22C55E' }
  if (t.includes('PPT')) return { icon: 'pptx', color: '#F59E0B' }
  if (t.includes('MD') || t.includes('TXT')) return { icon: 'file', color: '#64748B' }
  return { icon: 'file', color: '#94A3B8' }
}

function fmtTime(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
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

/* ---------- 上传 ---------- */
async function onUploadFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length) return
  if (!selectedKb.value) {
    toast.warning('请先在上方选择知识库')
    input.value = ''
    return
  }
  uploading.value = true
  let ok = 0
  for (const f of files) {
    try {
      const b64 = await readFileB64(f)
      await uploadDocument(selectedKb.value, f.name, b64)
      ok++
    } catch (err: any) {
      toast.error(`上传失败：${f.name} - ${err?.message || err}`)
    }
  }
  uploading.value = false
  input.value = ''
  if (ok) {
    toast.success(`成功上传 ${ok} 篇文档`)
    await loadDocs()
  }
}

/* ---------- 审核 / 删除 ---------- */
async function onApprove(doc: DocumentItem) {
  if (!selectedKb.value) return
  try {
    await approveDocument(selectedKb.value, doc.id)
    toast.success(`已通过审核：${doc.title}`)
    await loadDocs()
  } catch (e: any) {
    toast.error(`操作失败：${e?.message || e}`)
  }
}

async function onReject(doc: DocumentItem) {
  if (!selectedKb.value) return
  try {
    await rejectDocument(selectedKb.value, doc.id)
    toast.success(`已驳回：${doc.title}`)
    await loadDocs()
  } catch (e: any) {
    toast.error(`操作失败：${e?.message || e}`)
  }
}

async function onDelete(doc: DocumentItem) {
  if (!selectedKb.value) return
  if (!confirm(`确认删除文档「${doc.title}」？该操作会级联清理向量与图谱数据。`)) return
  deleting.value = true
  try {
    await deleteDocument(selectedKb.value, doc.id)
    toast.success(`已删除：${doc.title}`)
    await loadDocs()
  } catch (e: any) {
    toast.error(`删除失败：${e?.message || e}`)
  } finally {
    deleting.value = false
  }
}

/* ---------- 预览 ---------- */
async function onPreview(doc: DocumentItem) {
  if (!selectedKb.value) return
  previewLoading.value = true
  previewDoc.value = null
  try {
    previewDoc.value = await getDocument(selectedKb.value, doc.id)
  } catch (e: any) {
    toast.error(`预览失败：${e?.message || e}`)
  } finally {
    previewLoading.value = false
  }
}

/* ---------- AI 审核 ---------- */
async function onAiReview(doc: DocumentItem) {
  if (!selectedKb.value) return
  aiReviewLoading.value = true
  aiReview.value = null
  try {
    aiReview.value = await aiReviewDocument(selectedKb.value, doc.id)
  } catch (e: any) {
    toast.error(`AI 审核失败：${e?.message || e}`)
  } finally {
    aiReviewLoading.value = false
  }
}

/* ---------- 批量选择 / 删除 ---------- */
function toggleSelect(id: string) {
  const i = selectedIds.value.indexOf(id)
  if (i >= 0) selectedIds.value.splice(i, 1)
  else selectedIds.value.push(id)
}
function isSelected(id: string) {
  return selectedIds.value.includes(id)
}
function toggleSelectAllOnPage() {
  const pageIds = pagedDocs.value.map((d) => d.id)
  const allSelected = pageIds.every((id) => selectedIds.value.includes(id))
  if (allSelected) {
    selectedIds.value = selectedIds.value.filter((id) => !pageIds.includes(id))
  } else {
    const set = new Set(selectedIds.value)
    pageIds.forEach((id) => set.add(id))
    selectedIds.value = Array.from(set)
  }
}
function clearSelection() {
  selectedIds.value = []
}

async function onBatchDelete() {
  if (!selectedIds.value.length || !selectedKb.value) return
  const n = selectedIds.value.length
  if (!confirm(`确认批量删除选中的 ${n} 篇文档？该操作不可恢复。`)) return
  deleting.value = true
  let ok = 0
  for (const id of [...selectedIds.value]) {
    try {
      await deleteDocument(selectedKb.value, id)
      ok++
    } catch (e: any) {
      toast.error(`删除失败：${e?.message || e}`)
    }
  }
  deleting.value = false
  selectedIds.value = []
  toast.success(`已删除 ${ok}/${n} 篇文档`)
  await loadDocs()
}

/* ---------- 分页跳转 ---------- */
function goPage(p: number) {
  if (p >= 1 && p <= totalPages.value) currentPage.value = p
}
</script>

<template>
  <div class="docs-page">
    <h2 class="page-title">文档管理</h2>

    <!-- 分区说明横幅 -->
    <div v-if="section === 'public' || section === 'department'" class="scope-banner">
      <Icon name="info" :size="14" />
      <span>{{ section === 'public' ? '公共文档' : '部门文档' }}：后端暂未区分文档的公开 / 部门范围，当前展示全部文档。接口接入后将按范围筛选。</span>
    </div>
    <div v-else-if="section === 'archive'" class="scope-banner warn">
      <Icon name="archive" :size="14" />
      <span>文档归档：展示状态为「已拒绝」的文档。</span>
    </div>

    <!-- ====== 工具栏 ====== -->
    <div class="toolbar card">
      <div class="toolbar-left">
        <!-- 搜索 -->
        <div class="search-box">
          <Icon name="search" :size="14" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索文档名称、内容、上传人等" class="search-input" />
          <button v-if="searchQuery" class="search-clear" @click="clearSearch">
            <Icon name="close" :size="12" />
          </button>
        </div>

        <!-- 批量上传 -->
        <label class="btn btn-primary btn-sm upload-btn" :class="{ 'is-loading': uploading }">
          <Icon name="upload" :size="13" /> {{ uploading ? '上传中…' : '批量上传' }}
          <input type="file" multiple accept=".md,.txt,.docx,.pdf" class="file-hidden" @change="onUploadFiles" />
        </label>

        <!-- 筛选下拉组 -->
        <CustomSelect v-model="filterType" :options="typeOptions" placeholder="文件类型" width="110px" />
        <CustomSelect v-model="filterStatus" :options="statusOptions" placeholder="解析状态" width="110px" />
        <CustomSelect v-model="filterScope" :options="scopeOptions" placeholder="权限范围" width="110px" />

        <!-- 刷新 -->
        <button class="icon-btn" title="刷新" :disabled="loading" @click="loadDocs">
          <Icon name="refresh" :size="15" :class="{ spin: loading }" />
        </button>
      </div>

      <div class="toolbar-right">
        <button class="view-toggle" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'">
          <Icon name="listview" :size="16" />
        </button>
        <button class="view-toggle" :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'">
          <Icon name="gridview" :size="16" />
        </button>
      </div>
    </div>

    <!-- ====== 批量操作条 ====== -->
    <Transition name="slide-down">
      <div v-if="selectedIds.length" class="batch-bar card">
        <span class="batch-count">已选 <b>{{ selectedIds.length }}</b> 篇</span>
        <button class="btn btn-danger btn-sm" :disabled="deleting" @click="onBatchDelete">
          <Icon name="trash" :size="13" /> 批量删除
        </button>
        <button class="btn btn-ghost btn-sm" @click="clearSelection">取消选择</button>
      </div>
    </Transition>

    <!-- ====== 列表 / 网格 ====== -->
    <div class="file-table-wrap card" v-if="viewMode === 'list'">
      <table class="file-table">
        <thead>
          <tr>
            <th class="col-check">
              <input
                type="checkbox"
                :checked="!!pagedDocs.length && pagedDocs.every((d) => isSelected(d.id))"
                @change="toggleSelectAllOnPage"
              />
            </th>
            <th>文档名称</th>
            <th>文件类型</th>
            <th class="col-sort">上传时间 <Icon name="arrow-up-down" :size="11" /></th>
            <th>上传人</th>
            <th>文档解析状态</th>
            <th>权限范围</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in pagedDocs" :key="d.id" :class="{ 'row-selected': isSelected(d.id) }">
            <td class="col-check">
              <input type="checkbox" :checked="isSelected(d.id)" @change="toggleSelect(d.id)" />
            </td>
            <td>
              <div class="file-name-cell">
                <span class="file-icon-sm" :style="{ background: fileMeta(d.type).color + '18', color: fileMeta(d.type).color }">
                  <Icon :name="fileMeta(d.type).icon" :size="15" />
                </span>
                <span class="file-name" :title="d.title">{{ d.title }}</span>
              </div>
            </td>
            <td><span class="type-text">{{ d.type }}</span></td>
            <td class="col-time">{{ fmtTime(d.updatedAt) }}</td>
            <td class="col-uploader">{{ auth.user?.displayName || '—' }}</td>
            <td><span class="status-tag" :class="statusType(d.status)">{{ statusLabel(d.status) }}</span></td>
            <td><span class="scope-tag">公开可见</span></td>
            <td>
              <div class="row-actions">
                <button class="action-btn" title="预览" @click="onPreview(d)"><Icon name="eye" :size="15" /></button>
                <button class="action-btn" title="通过审核" @click="onApprove(d)"><Icon name="check" :size="15" /></button>
                <button class="action-btn" title="驳回" @click="onReject(d)"><Icon name="close" :size="15" /></button>
                <button class="action-btn" title="AI 审核" @click="onAiReview(d)"><Icon name="sparkles" :size="15" /></button>
                <button class="action-btn" title="删除" @click="onDelete(d)"><Icon name="trash" :size="15" /></button>
              </div>
            </td>
          </tr>
          <tr v-if="!loading && !pagedDocs.length">
            <td colspan="8" class="empty-cell">
              {{ selectedKb ? '该知识库暂无文档，点击「上传文档」添加' : '请选择左侧知识库' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 网格视图 -->
    <div class="file-grid" v-else>
      <div
        v-for="d in pagedDocs"
        :key="d.id"
        class="doc-card"
        :class="{ 'row-selected': isSelected(d.id) }"
        @click="toggleSelect(d.id)"
      >
        <div class="doc-card-top">
          <span class="file-icon-sm" :style="{ background: fileMeta(d.type).color + '18', color: fileMeta(d.type).color }">
            <Icon :name="fileMeta(d.type).icon" :size="18" />
          </span>
          <span class="status-badge mini" :class="statusType(d.status)">{{ d.status }}</span>
        </div>
        <div class="doc-card-title" :title="d.title">{{ d.title }}</div>
        <div class="doc-card-meta">{{ d.type }} · {{ fmtTime(d.updatedAt) }}</div>
        <div class="doc-card-actions" @click.stop>
          <button class="action-btn" title="预览" @click="onPreview(d)"><Icon name="eye" :size="15" /></button>
          <button class="action-btn" title="通过审核" @click="onApprove(d)"><Icon name="check" :size="15" /></button>
          <button class="action-btn" title="驳回" @click="onReject(d)"><Icon name="close" :size="15" /></button>
          <button class="action-btn" title="AI 审核" @click="onAiReview(d)"><Icon name="sparkles" :size="15" /></button>
          <button class="action-btn" title="删除" @click="onDelete(d)"><Icon name="trash" :size="15" /></button>
        </div>
      </div>
      <div v-if="!loading && !pagedDocs.length" class="grid-empty">
        {{ selectedKb ? '该知识库暂无文档' : '请选择左侧知识库' }}
      </div>
    </div>

    <!-- ====== 分页 ====== -->
    <div class="pagination-bar card" v-if="filteredDocs.length">
      <div class="page-info">共 {{ filteredDocs.length }} 条</div>
      <div class="page-size">
        <select class="select page-size-select" v-model.number="pageSize">
          <option :value="10">10条/页</option>
          <option :value="20">20条/页</option>
          <option :value="50">50条/页</option>
        </select>
      </div>
      <div class="page-numbers">
        <button class="pg" :disabled="currentPage === 1" @click="goPage(currentPage - 1)">&lt;</button>
        <button
          v-for="p in totalPages"
          :key="p"
          class="pg"
          :class="{ active: p === currentPage }"
          @click="goPage(p)"
        >{{ p }}</button>
        <button class="pg" :disabled="currentPage === totalPages" @click="goPage(currentPage + 1)">&gt;</button>
      </div>
    </div>

    <!-- ====== 预览弹窗 ====== -->
    <AppModal :show="!!previewDoc" title="文档预览" wide @close="previewDoc = null">
      <div v-if="previewLoading" class="modal-hint">加载中…</div>
      <template v-else-if="previewDoc">
        <div class="preview-meta">
          <span class="type-text">{{ previewDoc.type }}</span>
          <span class="col-time">{{ fmtTime(previewDoc.updatedAt) }}</span>
          <span class="status-badge mini" :class="statusType(previewDoc.status)">{{ previewDoc.status }}</span>
        </div>
        <pre class="preview-body">{{ previewDoc.contentMd || '（无内容）' }}</pre>
      </template>
    </AppModal>

    <!-- ====== AI 审核弹窗 ====== -->
    <AppModal :show="!!aiReview" title="AI 辅助审核" wide @close="aiReview = null">
      <div v-if="aiReviewLoading" class="modal-hint">AI 分析中…</div>
      <template v-else-if="aiReview">
        <div class="ai-verdict" :class="aiReview.verdict">
          建议：{{ aiReview.verdict === 'approve' ? '通过' : aiReview.verdict === 'reject' ? '驳回' : '人工复核' }}
        </div>
        <p class="ai-summary">{{ aiReview.summary }}</p>
        <div v-if="aiReview.similarityFindings?.length" class="ai-section">
          <h4>相似文档</h4>
          <ul class="ai-list">
            <li v-for="(f, i) in aiReview.similarityFindings" :key="i">
              <span class="ai-sim">相似度 {{ (f.similarity * 100).toFixed(0) }}%</span>
              <span class="ai-doc">{{ f.docTitle }}</span>
              <p class="ai-snippet">{{ f.snippet }}</p>
            </li>
          </ul>
        </div>
        <div v-if="aiReview.qualityNotes?.length" class="ai-section">
          <h4>质量建议</h4>
          <ul class="ai-list"><li v-for="(q, i) in aiReview.qualityNotes" :key="i">{{ q }}</li></ul>
        </div>
        <div v-if="aiReview.outdatedFindings?.length" class="ai-section">
          <h4>过时内容</h4>
          <ul class="ai-list"><li v-for="(o, i) in aiReview.outdatedFindings" :key="i">{{ o }}</li></ul>
        </div>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.docs-page {
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

/* 分区说明横幅 */
.scope-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: var(--brand-soft);
  color: var(--text-secondary);
  font-size: 12.5px;
  line-height: 1.5;
}
.scope-banner :deep(svg) { color: var(--brand); flex-shrink: 0; }
.scope-banner.warn { background: var(--warning-soft); }
.scope-banner.warn :deep(svg) { color: var(--warning); }

/* ---- 工具栏 ---- */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  gap: 12px;
  flex-wrap: wrap;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

/* 搜索框 */
.search-box {
  position: relative;
  width: 240px;
}
.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-tertiary);
  pointer-events: none;
}
.search-input {
  width: 100%;
  height: 34px;
  padding: 0 30px 0 32px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
  background: var(--bg-surface);
  transition: all var(--dur-fast);
}
.search-input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.search-clear {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  color: var(--text-tertiary);
  cursor: pointer;
  background: transparent;
}
.search-clear:hover { background: var(--bg-hover); }

/* 上传按钮（label 包裹 input） */
.upload-btn { position: relative; overflow: hidden; cursor: pointer; }
.file-hidden {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
  width: 100%;
}
.upload-btn.is-loading { opacity: 0.7; pointer-events: none; }

.view-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 33px;
  height: 33px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--dur-fast);
}
.view-toggle:hover { background: var(--bg-hover); color: var(--text-secondary); }
.view-toggle.active { background: var(--brand); color: #fff; border-color: var(--brand); }
.icon-btn:disabled { opacity: 0.5; cursor: default; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 批量条 */
.batch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-left: 3px solid var(--brand);
}
.batch-count { font-size: 13px; color: var(--text-secondary); }
.batch-count b { color: var(--text-primary); }
.btn-danger { background: #DC2626; color: #fff; border-color: #DC2626; }
.btn-danger:hover { background: #B91C1C; }
.btn-danger:disabled { opacity: 0.6; }
.slide-down-enter-active, .slide-down-leave-active { transition: all 0.2s var(--ease-out); }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; transform: translateY(-6px); }

/* ---- 文件表格 ---- */
.file-table-wrap { overflow-x: auto; }
.file-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.file-table th {
  text-align: left;
  padding: 11px 14px;
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 12px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.file-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
.file-table tr:last-child td { border-bottom: none; }
.row-selected { background: var(--brand-soft); }
.col-check { width: 38px; text-align: center; }
.col-check input[type='checkbox'] { accent-color: var(--brand); width: 15px; height: 15px; }

.file-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 360px;
}
.file-icon-sm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  flex-shrink: 0;
}
.file-name {
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.type-text { color: var(--text-secondary); font-weight: 500; }
.col-time { color: var(--text-tertiary); white-space: nowrap; }
.col-sort { white-space: nowrap; color: var(--text-secondary); cursor: pointer; user-select: none; }
.col-sort:hover { color: var(--brand); }
.col-uploader { color: var(--text-secondary); }

/* 状态标签（原型风格） */
.status-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 11px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 500;
}
.status-tag.success { background: rgba(34,197,94,.10); color: #16a34a; }
.status-tag.warning { background: rgba(245,158,11,.12); color: #d97706; }
.status-tag.danger { background: rgba(239,68,68,.10); color: #dc2626; }

/* 权限范围标签 */
.scope-tag {
  display: inline-flex;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  background: rgba(59,130,246,.10);
  color: #2563eb;
}

/* 兼容旧 .status-badge */
.status-badge {
  display: inline-flex; align-items: center; padding: 2px 10px;
  border-radius: var(--radius-pill); font-size: 12px; font-weight: 500;
}
.status-badge.success { background: #D1FAE5; color: #065F46; }
.status-badge.warning { background: #FEF3C7; color: #92400E; }
.status-badge.danger { background: #FEE2E2; color: #991B1B; }
.status-badge.mini { padding: 1px 8px; font-size: 11px; }

.row-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  background: transparent;
  cursor: pointer;
  transition: all var(--dur-fast);
}
.action-btn:hover { background: var(--bg-hover); color: var(--text-primary); }

.empty-cell {
  text-align: center;
  color: var(--text-tertiary);
  padding: 32px 0 !important;
}

/* ---- 网格视图 ---- */
.file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}
.doc-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
  transition: all var(--dur-fast);
}
.doc-card:hover { border-color: var(--brand); box-shadow: var(--shadow-pop); }
.doc-card.row-selected { border-color: var(--brand); background: var(--brand-soft); }
.doc-card-top { display: flex; align-items: center; justify-content: space-between; }
.doc-card-title {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.doc-card-meta { font-size: 12px; color: var(--text-tertiary); }
.doc-card-actions {
  display: flex;
  gap: 2px;
  margin-top: 2px;
  opacity: 0.85;
}
.grid-empty {
  grid-column: 1 / -1;
  text-align: center;
  color: var(--text-tertiary);
  padding: 40px 0;
}

/* ---- 分页 ---- */
.pagination-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 16px;
  font-size: 13px;
  color: var(--text-secondary);
}
.page-info { white-space: nowrap; }
.page-size-select {
  height: 30px;
  padding: 0 8px;
  font-size: 12px;
  border-color: var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
}
.page-numbers { display: flex; align-items: center; gap: 4px; }
.pg {
  min-width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0 8px;
  font-family: inherit;
}
.pg:hover:not(:disabled) { border-color: var(--brand); color: var(--brand); }
.pg.active { background: var(--brand); color: #fff; border-color: var(--brand); }
.pg:disabled { opacity: 0.4; cursor: default; }

/* ---- 弹窗内容 ---- */
.modal-hint { color: var(--text-tertiary); text-align: center; padding: 20px 0; }
.preview-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 12px;
}
.preview-body {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
  line-height: 1.7;
  max-height: 52vh;
  overflow-y: auto;
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  padding: 14px;
  margin: 0;
  color: var(--text-secondary);
}
.ai-verdict {
  display: inline-block;
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 10px;
}
.ai-verdict.approve { background: #D1FAE5; color: #065F46; }
.ai-verdict.reject { background: #FEE2E2; color: #991B1B; }
.ai-verdict.manual_review, .ai-verdict.manual { background: #FEF3C7; color: #92400E; }
.ai-summary { margin: 0 0 14px; color: var(--text-secondary); line-height: 1.6; }
.ai-section h4 { font-size: 13px; color: var(--text-primary); margin: 14px 0 6px; }
.ai-list { margin: 0; padding-left: 18px; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.ai-list li { margin-bottom: 8px; }
.ai-sim { color: var(--brand); font-weight: 600; margin-right: 8px; }
.ai-doc { font-weight: 500; color: var(--text-primary); }
.ai-snippet { margin: 4px 0 0; color: var(--text-tertiary); font-size: 12px; }
</style>
