<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import Icon from '@/components/Icon.vue'
import { getDocuments, uploadDocument, getDocument, approveDocument, rejectDocument, deleteDocument } from '@/api'
import type { DocumentItem, DocumentDetail } from '@/types/api'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useSidebarCollapsed } from '@/composables/useSidebarCollapsed'

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
  icon: string
  description: string
}> = {
  compliance: {
    name: '合规库',
    icon: 'compliance',
    description: '亚马逊平台合规政策、产品认证标准、知识产权法规等文档集合。',
  },
  ads: {
    name: '广告投放',
    icon: 'ads',
    description: 'PPC 广告策略、关键词优化、品牌推广、Sponsored Products 等实操指南。',
  },
  logistics: {
    name: '物流仓储',
    icon: 'logistics',
    description: 'FBA/FBM 物流方案、仓储管理、头程运输、清关流程、退换货处理。',
  },
  selection: {
    name: '选品策略',
    icon: 'selection',
    description: '市场调研方法论、竞品分析框架、选品工具使用、利润测算模板。',
  },
  service: {
    name: '客服话术',
    icon: 'service',
    description: '售前咨询话术、售后纠纷处理、Review 管理、客户沟通 SOP。',
  },
}

const kbId = computed(() => route.params.id as string)
// 头部信息：优先用 store 里真实的库名/图标，description 回退到 kbMap
const kb = computed(() => {
  const s = knowledgeStore.bases.find(b => b.id === kbId.value)
  const base = kbMap[kbId.value] || { name: '未知', icon: 'library', description: '' }
  return {
    name: s?.name || base.name,
    icon: s?.icon || base.icon,
    description: base.description,
  }
})

/* 真实文档列表（接 /api/knowledge-bases/:id/documents） */
const documents = ref<DocumentItem[]>([])
const loadingDocs = ref(false)
const uploadError = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

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

function triggerUpload() {
  fileInput.value?.click()
}

async function onFilePicked(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // 允许重复选同一文件
  if (!file) return
  if (!/\.(md|markdown|txt|docx|pdf)$/i.test(file.name)) {
    uploadError.value = `仅支持 .md / .txt / .docx / .pdf，当前文件：${file.name}`
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
  }
}

/* ── 文档操作：查看 / 审核通过 / 驳回 / 删除 ── */
const detailDoc = ref<DocumentDetail | null>(null)
const loadingDetail = ref(false)

function statusClass(s: string): string {
  if (s === '已审核') return ''
  if (s === '待复核') return 'pending'
  return 'rejected'
}

async function openDetail(doc: DocumentItem) {
  loadingDetail.value = true
  detailDoc.value = null
  try {
    detailDoc.value = await getDocument(kbId.value, doc.id)
  } catch (e) {
    console.error('加载详情失败', e)
  } finally {
    loadingDetail.value = false
  }
}

function closeDetail() {
  detailDoc.value = null
}

async function approve(doc: DocumentItem) {
  try {
    await approveDocument(kbId.value, doc.id)
    await loadDocuments()
  } catch (e) {
    console.error('审核通过失败', e)
  }
}

async function reject(doc: DocumentItem) {
  try {
    await rejectDocument(kbId.value, doc.id)
    await loadDocuments()
  } catch (e) {
    console.error('驳回失败', e)
  }
}

async function remove(doc: DocumentItem) {
  if (!confirm(`确定删除「${doc.title}」？该操作会同时清理检索索引，不可恢复。`)) return
  try {
    await deleteDocument(kbId.value, doc.id)
    await loadDocuments()
    if (detailDoc.value?.id === doc.id) detailDoc.value = null
  } catch (e) {
    console.error('删除失败', e)
  }
}

onMounted(() => {
  syncMobile()
  mq = window.matchMedia('(max-width: 900px)')
  mq.addEventListener('change', syncMobile)
  loadDocuments()
})
onUnmounted(() => mq?.removeEventListener('change', syncMobile))
watch(() => route.params.id, () => loadDocuments())
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
          <div class="kb-header-icon"><Icon :name="kb.icon" :size="28" /></div>
          <div class="kb-header-info">
            <h2 class="kb-title">{{ kb.name }}</h2>
            <p class="kb-desc">{{ kb.description }}</p>
            <span class="kb-meta">{{ documents.length }} 篇文档</span>
          </div>
        </div>

        <!-- 操作栏 -->
        <div class="toolbar">
          <button class="btn-primary" @click="triggerUpload" :disabled="loadingDocs">
            <Icon name="plus" :size="16" />
            {{ loadingDocs ? '上传中...' : '上传文档' }}
          </button>
          <div class="toolbar-right">
            <input type="text" placeholder="搜索文档..." class="search-input" />
          </div>
        </div>
        <p v-if="uploadError" class="upload-error">{{ uploadError }}</p>

        <!-- 文档列表 -->
        <div class="doc-list">
          <div v-for="doc in documents" :key="doc.id" class="doc-item">
            <div class="doc-icon">
              <Icon name="library" :size="18" />
            </div>
            <div class="doc-info">
              <span class="doc-title">{{ doc.title }}</span>
              <span class="doc-meta">{{ doc.type }} · {{ doc.sizeKb }} KB</span>
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
    <div v-if="detailDoc" class="modal-mask" @click.self="closeDetail">
      <div class="modal">
        <div class="modal-head">
          <div class="modal-title">
            <span class="doc-title">{{ detailDoc.title }}</span>
            <span class="doc-status" :class="statusClass(detailDoc.status)">{{ detailDoc.status }}</span>
          </div>
          <button class="modal-close" @click="closeDetail">
            <Icon name="plus" :size="16" style="transform: rotate(45deg)" />
          </button>
        </div>
        <div class="modal-meta">
          {{ detailDoc.type }} · {{ detailDoc.fileSize ? Math.round(detailDoc.fileSize / 1024 * 10) / 10 + ' KB' : '—' }}
          <template v-if="detailDoc.originalFilename"> · {{ detailDoc.originalFilename }}</template>
        </div>
        <div v-if="loadingDetail" class="detail-loading">加载中...</div>
        <pre v-else class="detail-content">{{ detailDoc.contentMd }}</pre>
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
.kb-header-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  background: var(--brand-soft);
  color: var(--brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
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
  padding: 9px 18px;
  background: var(--brand);
  color: #fff;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
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

/* 详情弹窗 */
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
  max-height: 84vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-float);
  padding: 22px 22px 18px;
}
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
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
  margin: 8px 0 14px;
  font-size: 12px;
  color: var(--text-placeholder);
}
.detail-loading {
  padding: 24px 0;
  text-align: center;
  color: var(--text-placeholder);
  font-size: 13px;
}
.detail-content {
  margin: 0;
  padding: 16px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  overflow-y: auto;
  max-height: 56vh;
}

@media (max-width: 900px) {
  .main {
    padding-top: var(--mobile-topbar-h);
  }
  .body {
    padding: 16px;
  }
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .toolbar-right {
    max-width: none;
  }
  .kb-header { padding: 16px; flex-direction: column; align-items: center; text-align: center; }
  .doc-actions { display: none; }
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
