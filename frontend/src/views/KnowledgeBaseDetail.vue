<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import Icon from '@/components/Icon.vue'
import { getDocuments, uploadDocument } from '@/api'
import type { DocumentItem } from '@/types/api'
import { useSidebarCollapsed } from '@/composables/useSidebarCollapsed'

const route = useRoute()
const { collapsed } = useSidebarCollapsed()

function onCollapse() {
  collapsed.value = true
}

function onExpand() {
  collapsed.value = false
}

/* 硬数据 —— 详情页头部信息（详情接口留后续对接） */
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
const kb = computed(() => kbMap[kbId.value] || { name: '未知', icon: 'library', description: '' })

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
  if (!/\.(md|markdown|txt)$/i.test(file.name)) {
    uploadError.value = `仅支持 .md / .txt，当前文件：${file.name}`
    return
  }
  uploadError.value = null
  try {
    const content = await file.text()
    await uploadDocument(kbId.value, file.name, content)
    await loadDocuments()
  } catch (e) {
    uploadError.value = e instanceof Error ? e.message : String(e)
  }
}

onMounted(loadDocuments)
watch(() => route.params.id, () => loadDocuments())
</script>

<template>
  <div class="kb-detail-page">
    <AppSidebar :collapsed="collapsed" @collapse="onCollapse" @expand="onExpand" />
    <div class="main">
      <TopBar :title="kb.name" />
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
            <span class="doc-status" :class="doc.status === '待复核' ? 'pending' : ''">
              {{ doc.status }}
            </span>
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
          accept=".md,.markdown,.txt"
          class="hidden-file"
          @change="onFilePicked"
        />
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

@media (max-width: 900px) {
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
}
</style>
