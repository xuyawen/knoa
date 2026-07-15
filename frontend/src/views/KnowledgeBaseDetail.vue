<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import Icon from '@/components/Icon.vue'
import AIReviewPanel from '@/components/AIReviewPanel.vue'
import { getDocuments, uploadDocument, getDocument, approveDocument, rejectDocument, deleteDocument, aiReviewDocument } from '@/api'
import type { DocumentItem, DocumentDetail, AIReview } from '@/types/api'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useSidebarCollapsed } from '@/composables/useSidebarCollapsed'
import { useConfirm } from '@/composables/useConfirm'

const { confirm } = useConfirm()

const route = useRoute()
const router = useRouter()
const { collapsed } = useSidebarCollapsed()
const knowledgeStore = useKnowledgeStore()

function onCollapse() {
  collapsed.value = true
}

function onExpand() {
  collapsed.value = false
}

const isMobile = ref(false)
const drawer = ref(false)
let mq: MediaQueryList | undefined

function syncMobile() {
  isMobile.value = window.matchMedia('(max-width: 900px)').matches
}

/* 硬数据兜底 —— 详情页头部信息（store 无 description 字段时回退） */
const kbMap: Record<string, {
  name: string
  description: string
}> = {
  compliance: {
    name: '合规库',
    description: '亚马逊平台合规政策、产品认证标准、知识产权法规等文档集合。',
  },
  ads: {
    name: '广告投放',
    description: 'PPC 广告策略、关键词优化、品牌推广、Sponsored Products 等实操指南。',
  },
  logistics: {
    name: '物流仓储',
    description: 'FBA/FBM 物流方案、仓储管理、头程运输、清关流程、退换货处理。',
  },
  selection: {
    name: '选品策略',
    description: '市场调研方法论、竞品分析框架、选品工具使用、利润测算模板。',
  },
  service: {
    name: '客服话术',
    description: '售前咨询话术、售后纠纷处理、Review 管理、客户沟通 SOP。',
  },
}

const kbId = computed(() => route.params.id as string)
// 头部信息：优先用 store 里真实的库名，description 回退到 kbMap
const kb = computed(() => {
  const s = knowledgeStore.bases.find(b => b.id === kbId.value)
  const base = kbMap[kbId.value] || { name: '未知', description: '' }
  return {
    name: s?.name || base.name,
    description: base.description,
  }
})

/* 真实文档列表（接 /api/knowledge-bases/:id/documents） */
const documents = ref<DocumentItem[]>([])
const loadingDocs = ref(false)
const isUploading = ref(false)
const uploadError = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const docSearch = ref('')

// 文档列表本地关键字过滤（按标题）
const filteredDocs = computed(() => {
  const q = docSearch.value.trim().toLowerCase()
  if (!q) return documents.value
  return documents.value.filter((d) => d.title.toLowerCase().includes(q))
})

async function loadDocuments() {
  loadingDocs.value = true
  uploadError.value = null
  try {
    documents.value = await getDocuments(kbId.value)
  } catch (e) {
    console.error('加载文档失败', e)
  } finally {
    loadingDocs.value = false
  }
}

async function triggerUpload() {
  isUploading.value = true
  try {
    fileInput.value?.click()
  } finally {
    setTimeout(() => { isUploading.value = false }, 100) // 点一下立刻恢复，避免文件选择器关闭后长时间 disabled
  }
}

async function onFilePicked(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // 允许重复选同一文件
  if (!file) return
  if (!/\.(md|markdown|txt|docx|pdf)$/i.test(file.name)) {
    uploadError.value = `仅支持 .md / .txt / .docx / .pdf，当前文件：${file.name}`
    isUploading.value = false
    return
  }
  uploadError.value = null
  try {
    // 把文件读成 base64 原始字节；二进制格式（docx/pdf）只能走 base64
    const buf = await file.arrayBuffer()
    const bytes = new Uint8Array(buf)
    let binary = ''
    const chunk = 0x8000
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk) as unknown as number[])
    }
    const b64 = btoa(binary)
    // 方案 A：上传只落库不摄入，状态=待复核，列表立即可见但检索不可见
    await uploadDocument(kbId.value, file.name, b64)
    await loadDocuments()
  } catch (e) {
    uploadError.value = e instanceof Error ? e.message : String(e)
  } finally {
    isUploading.value = false
  }
}

/* ── 文档操作：查看 / 审核通过 / 驳回 / 删除 ── */
const detailOpen = ref(false)
const detailDoc = ref<DocumentDetail | null>(null)
const loadingDetail = ref(false)

/* 当前操作的文档项（带 sizeKb 等列表字段） */
const currentDoc = ref<DocumentItem | null>(null)

/* AI 审核建议 */
const reviewResult = ref<AIReview | null>(null)
const loadingReview = ref(false)

/* 文档正文折叠 */
const showFullContent = ref(false)

async function openReview(doc: DocumentItem) {
  loadingReview.value = true
  reviewResult.value = null
  try {
    reviewResult.value = await aiReviewDocument(kbId.value, doc.id)
  } catch (e) {
    console.error('AI 审核失败', e)
    reviewResult.value = {
      verdict: 'manual_review',
      summary: 'AI 审核失败，请手动审核。',
      duplicates: [],
      outdatedFindings: [],
      qualityNotes: [],
      suggestedKb: null,
      similarityFindings: [],
    }
  } finally {
    loadingReview.value = false
  }
}

function statusClass(s: string): string {
  if (s === '已审核') return ''
  if (s === '待复核') return 'pending'
  return 'rejected'
}

function formatDocTime(iso: string): string {
  try {
    const d = new Date(iso)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const h = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    return `${y}-${m}-${day} ${h}:${min}`
  } catch {
    return iso
  }
}

async function openDetail(doc: DocumentItem) {
  detailOpen.value = true
  currentDoc.value = doc
  loadingDetail.value = true
  detailDoc.value = null
  reviewResult.value = null
  showFullContent.value = false
  try {
    detailDoc.value = await getDocument(kbId.value, doc.id)
  } catch (e) {
    console.error('加载详情失败', e)
  } finally {
    loadingDetail.value = false
  }
}

function closeDetail() {
  detailOpen.value = false
  detailDoc.value = null
  currentDoc.value = null
  reviewResult.value = null
  showFullContent.value = false
}

async function approve(doc: DocumentItem) {
  try {
    await approveDocument(kbId.value, doc.id)
    await loadDocuments()
    knowledgeStore.reload() // 刷新侧边栏 pendingCount
    closeDetail()
  } catch (e) {
    console.error('审核通过失败', e)
  }
}

async function reject(doc: DocumentItem) {
  try {
    await rejectDocument(kbId.value, doc.id)
    await loadDocuments()
    knowledgeStore.reload() // 刷新侧边栏 pendingCount
    closeDetail()
  } catch (e) {
    console.error('驳回失败', e)
  }
}

async function remove(doc: DocumentItem) {
  const ok = await confirm({
    title: '删除文档',
    message: `确定删除「${doc.title}」？该操作会同时清理检索索引，不可恢复。`,
    confirmText: '删除',
    danger: true,
    onConfirm: async () => {
      await deleteDocument(kbId.value, doc.id)
      await loadDocuments()
      if (currentDoc.value?.id === doc.id) closeDetail()
    },
  })
  if (!ok) return
}

onMounted(() => {
  syncMobile()
  mq = window.matchMedia('(max-width: 900px)')
  mq.addEventListener('change', syncMobile)
  loadDocuments()
})
onUnmounted(() => {
  syncMobile()
  loadDocuments()
  mq?.removeEventListener('change', syncMobile)
})
watch(() => route.params.id, () => {
  syncMobile()
  loadDocuments()
})
</script>

<template>
  <div class="kb-detail-page">
    <AppSidebar :collapsed="collapsed" :mobile-open="drawer" @collapse="onCollapse" @expand="onExpand" @close="drawer = false" />
    <div v-if="isMobile && drawer" class="overlay" @click="drawer = false" />

    <!-- 移动端顶栏 -->
    <header v-if="isMobile" class="m-top">
      <button class="m-menu" @click="drawer = true" title="菜单">
        <Icon name="menu" :size="20" />
      </button>
      <span class="m-title">{{ kb.name }}</span>
      <button class="m-back" @click="router.push('/knowledge-bases')">返回</button>
    </header>

    <div class="main">
      <TopBar v-if="!isMobile" :title="kb.name" />
      <div class="body">
        <!-- 面包屑 -->
        <nav class="breadcrumb">
          <router-link to="/knowledge-bases" class="crumb-link">知识库</router-link>
          <span class="crumb-sep">/</span>
          <span class="crumb-current">{{ kb.name }}</span>
        </nav>

        <!-- 库信息卡片 -->
        <div class="kb-header">
          <div class="kb-header-info">
            <h2 class="kb-title">{{ kb.name }}</h2>
            <p class="kb-desc">{{ kb.description }}</p>
            <span class="kb-meta">{{ documents.length }} 篇文档</span>
          </div>
        </div>

        <!-- 操作栏 -->
        <div class="toolbar">
          <button class="btn-primary" @click="triggerUpload" :disabled="isUploading">
            <Icon name="plus" :size="16" />
            {{ isUploading ? '上传中...' : '上传文档' }}
          </button>
          <div class="toolbar-right">
            <input v-model="docSearch" type="text" placeholder="搜索文档..." class="search-input" />
          </div>
        </div>
        <p v-if="uploadError" class="upload-error">{{ uploadError }}</p>

        <!-- 文档列表 -->
        <div class="doc-list">
          <div v-for="doc in filteredDocs" :key="doc.id" class="doc-item">
            <div class="doc-icon">
              <Icon name="library" :size="18" />
            </div>
            <div class="doc-info">
              <span class="doc-title">{{ doc.title }}</span>
              <span class="doc-meta">{{ doc.type }} · {{ doc.sizeKb }} KB · {{ formatDocTime(doc.updatedAt) }}</span>
            </div>
            <span class="doc-status" :class="statusClass(doc.status)">
              {{ doc.status }}
            </span>
            <!-- 行内操作 -->
            <div class="doc-actions">
              <button class="act" title="查看" @click="openDetail(doc)">
                <Icon name="search" :size="15" />
              </button>
              <template v-if="doc.status === '待复核'">
                <button class="act approve" title="审核通过" @click="approve(doc)">
                  <Icon name="check" :size="15" />
                </button>
                <button class="act reject" title="驳回" @click="reject(doc)">
                  <Icon name="thumb-down" :size="15" />
                </button>
              </template>
              <button class="act danger" title="删除" @click="remove(doc)">
                <Icon name="trash" :size="15" />
              </button>
            </div>
          </div>

          <div v-if="!loadingDocs && documents.length === 0" class="empty-state">
            <Icon name="library" :size="36" />
            <p>暂无文档，点击上方按钮上传</p>
          </div>
          <div v-else-if="!loadingDocs && filteredDocs.length === 0" class="empty-state">
            <Icon name="search" :size="36" />
            <p>没有匹配「{{ docSearch }}」的文档</p>
          </div>
          <div v-if="loadingDocs" class="empty-state">
            <p>加载中...</p>
          </div>
        </div>

        <!-- 隐藏的文件选择 -->
        <input
          ref="fileInput"
          type="file"
          accept=".md,.markdown,.txt,.docx,.pdf"
          class="hidden-file"
          @change="onFilePicked"
        />
      </div>
    </div>

    <!-- 文档详情弹窗（只读预览 content_md） -->
    <div v-if="detailOpen" class="modal-mask" @click.self="closeDetail">
      <div class="modal">
        <!-- 固定头部 -->
        <div class="modal-head">
          <div class="modal-title">
            <span class="doc-title">{{ detailDoc?.title ?? currentDoc?.title }}</span>
            <span v-if="detailDoc" class="doc-status" :class="statusClass(detailDoc.status)">{{ detailDoc.status }}</span>
          </div>
          <button class="modal-close" @click="closeDetail">
            <Icon name="plus" :size="16" style="transform: rotate(45deg)" />
          </button>
        </div>

        <!-- 固定操作栏（仅待复核；滚动时长驻可见） -->
        <div v-if="detailDoc?.status === '待复核'" class="modal-actions">
          <button class="btn-approve" @click="approve(currentDoc!)" :disabled="loadingReview">
            <Icon name="check" :size="15" /> 审核通过
          </button>
          <button class="btn-reject" @click="reject(currentDoc!)">
            <Icon name="thumb-down" :size="15" /> 驳回
          </button>
          <button class="btn-review" @click="openReview(currentDoc!)" :disabled="loadingReview">
            <Icon name="sparkle" :size="15" />
            {{ loadingReview ? 'AI 审核中…' : 'AI 辅助审核' }}
          </button>
        </div>

        <!-- 滚动内容区 -->
        <div class="modal-body">
          <div v-if="loadingDetail" class="detail-loading">
            <span class="spinner" /> 加载中…
          </div>

          <template v-else-if="detailDoc">
            <div class="modal-meta">
              {{ detailDoc.type }} · {{ detailDoc.fileSize ? Math.round(detailDoc.fileSize / 1024 * 10) / 10 + ' KB' : '—' }}
              <template v-if="detailDoc.originalFilename"> · {{ detailDoc.originalFilename }}</template>
            </div>

            <!-- 文档正文：可折叠预览 -->
            <div v-if="showFullContent" class="content-wrapper content-wrapper--full">
              <pre class="detail-content">{{ detailDoc.contentMd }}</pre>
            </div>
            <div v-else class="content-wrapper">
              <pre class="detail-content content-preview">{{ detailDoc.contentMd }}</pre>
              <button class="expand-btn" @click="showFullContent = true"><Icon name="chevron-up" :size="12" /> 展开完整内容</button>
            </div>

            <!-- AI 审核建议面板 -->
            <AIReviewPanel v-if="reviewResult" :review="reviewResult" :loading="loadingReview" />
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kb-detail-page {
  display: flex;
  height: 100%;
  overflow-x: hidden;
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.body {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
}

/* 面包屑 */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 18px;
  font-size: 13px;
}
.crumb-link {
  color: var(--brand);
  transition: opacity 0.15s ease;
}
.crumb-link:hover {
  opacity: 0.75;
}
.crumb-sep {
  color: var(--text-placeholder);
}
.crumb-current {
  color: var(--text-secondary);
}

/* 库信息卡片 */
.kb-header {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  padding: 24px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  margin-bottom: 20px;
}
.kb-header-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.kb-title {
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
}
.kb-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.kb-meta {
  font-size: 12px;
  color: var(--text-placeholder);
}

/* 操作栏 */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 12px;
}
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: var(--btn-padding-md);
  background: var(--brand);
  color: #fff;
  border-radius: var(--radius-md);
  font-size: var(--btn-font-size);
  font-weight: var(--btn-font-weight);
  transition: background 0.15s ease, transform 0.15s ease;
}
.btn-primary:hover {
  background: var(--brand-hover);
  transform: translateY(-1px);
}
.toolbar-right {
  flex: 1;
  max-width: 320px;
}
.search-input {
  width: 100%;
  padding: 8px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s ease;
}
.search-input:focus {
  border-color: var(--brand);
}
.upload-error {
  margin: -8px 0 12px;
  font-size: 12px;
  color: var(--danger);
}
.hidden-file {
  display: none;
}

/* 文档列表 */
.doc-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.doc-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.doc-item:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-card);
}
.doc-icon {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.doc-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.doc-title {
  font-size: 14px;
  font-weight: 500;
}
.doc-meta {
  font-size: 12px;
  color: var(--text-placeholder);
}
.doc-status {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  white-space: nowrap;
  background: var(--success);
  color: #fff;
  opacity: 0.85;
}
.doc-status.pending {
  background: var(--warning);
  color: #fff;
}
.doc-status.rejected {
  background: var(--danger);
  color: #fff;
}
/* 行内操作 */
.doc-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.act {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  transition: background 0.15s ease, color 0.15s ease;
}
.act:hover {
  background: var(--brand-soft);
  color: var(--brand);
}
.act.approve:hover {
  background: var(--success-soft);
  color: var(--success);
}
.act.reject:hover {
  background: var(--warning-soft);
  color: var(--warning);
}
.act.danger:hover {
  background: var(--danger-soft);
  color: var(--danger);
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 0;
  color: var(--text-placeholder);
}
.empty-state p {
  font-size: 14px;
}

/* ── 文档正文折叠容器 ── */
.detail-content {
  margin: 0;
  padding: 12px 16px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 56vh;
  overflow-y: auto;
}

/* 折叠态：底部渐变遮罩提示还有更多内容 */
.detail-content.content-preview {
  display: -webkit-box;
  -webkit-line-clamp: 8;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  max-height: none;
  margin-bottom: 0;
}

/* 折叠态外层包裹渐变遮罩（带圆角） */
.content-wrapper {
  position: relative;
  border-bottom-left-radius: var(--radius-md);
  border-bottom-right-radius: var(--radius-md);
  overflow: hidden;
}

/* 折叠态外层包裹渐变遮罩 */
.content-wrapper::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 48px;
  pointer-events: none;
  background: linear-gradient(to top, var(--bg-subtle) 0%, transparent 100%);
  opacity: 1;
  transition: opacity 0.2s ease;
}

/* 展开后：恢复正常布局，隐藏渐变遮罩 */
.content-wrapper--full {
  border-bottom-left-radius: var(--radius-md);
  border-bottom-right-radius: var(--radius-md);
  overflow: visible;
}
.content-wrapper--full::after {
  display: none;
}

/* 渐变遮罩下的展开按钮 */
.expand-btn {
  position: absolute;
  bottom: 10px;
  right: 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--brand);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition: all 0.2s ease;
  z-index: 2;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.expand-btn:hover {
  background: var(--brand);
  color: #fff;
  border-color: var(--brand);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* ── 详情弹窗 ── */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 60;
}
.modal {
  width: 640px;
  max-width: calc(100vw - 32px);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-float);
  overflow: hidden;
  padding: 0;
  gap: 0;
}
.modal-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 22px 14px;
  border-bottom: 1px solid var(--border);
}
.modal-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.modal-title .doc-title {
  font-size: 16px;
  font-weight: 600;
}
.modal-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  flex-shrink: 0;
  transition: background 0.15s ease;
}
.modal-close:hover {
  background: var(--bg-subtle);
}
.modal-meta {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--text-placeholder);
}
.modal-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 22px 20px;
}
.detail-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 32px 0;
  color: var(--text-placeholder);
  font-size: 13px;
}
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--brand);
  border-radius: 50%;
  animation: modal-spin 0.7s linear infinite;
}
@keyframes modal-spin {
  to { transform: rotate(360deg); }
}

/* ── 审核操作按钮（固定栏，滚动时常驻） ── */
.modal-actions {
  flex-shrink: 0;
  display: flex;
  gap: 8px;
  padding: 12px 22px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-subtle);
}
.btn-approve,
.btn-reject,
.btn-review {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 13px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, transform 0.15s ease;
  white-space: nowrap;
}
.btn-approve {
  background: var(--success);
  color: #fff;
}
.btn-approve:hover:not(:disabled) {
  background: #059669;
  transform: translateY(-1px);
}
.btn-reject {
  background: var(--warning);
  color: #fff;
}
.btn-reject:hover:not(:disabled) {
  background: #D97706;
  transform: translateY(-1px);
}
.btn-review {
  background: var(--brand);
  color: #fff;
  margin-left: auto;
}
.btn-review:hover:not(:disabled) {
  background: var(--brand-hover);
  transform: translateY(-1px);
}
.btn-approve:disabled,
.btn-reject:disabled,
.btn-review:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

/* 移动端顶栏 */
.m-top {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: var(--mobile-topbar-h);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  z-index: 30;
}
.m-menu {
  width: 36px; height: 36px;
  border-radius: var(--radius-pill);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-primary);
}
.m-title {
  font-family: var(--font-display); font-size: 16px; font-weight: 600;
}
.m-back {
  margin-left: auto;
  font-size: 13px; color: var(--brand); font-weight: 500;
  background: none; border: none;
  cursor: pointer;
}
.overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 35;
}
</style>
