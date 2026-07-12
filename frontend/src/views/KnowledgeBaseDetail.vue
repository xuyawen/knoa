<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import Icon from '@/components/Icon.vue'

const route = useRoute()

const collapsed = ref(false)

/* 硬数据 —— 后续对接 /api/knowledge-bases/:id 接口替换 */
const kbMap: Record<string, {
  name: string
  icon: string
  description: string
  docCount: number
  updatedAt: string
}> = {
  compliance: {
    name: '合规库',
    icon: 'compliance',
    description: '亚马逊平台合规政策、产品认证标准、知识产权法规等文档集合。',
    docCount: 10,
    updatedAt: '22 小时前更新',
  },
  ads: {
    name: '广告投放',
    icon: 'ads',
    description: 'PPC 广告策略、关键词优化、品牌推广、Sponsored Products 等实操指南。',
    docCount: 10,
    updatedAt: '22 小时前更新',
  },
  logistics: {
    name: '物流仓储',
    icon: 'logistics',
    description: 'FBA/FBM 物流方案、仓储管理、头程运输、清关流程、退换货处理。',
    docCount: 10,
    updatedAt: '22 小时前更新',
  },
  selection: {
    name: '选品策略',
    icon: 'selection',
    description: '市场调研方法论、竞品分析框架、选品工具使用、利润测算模板。',
    docCount: 10,
    updatedAt: '22 小时前更新',
  },
  service: {
    name: '客服话术',
    icon: 'service',
    description: '售前咨询话术、售后纠纷处理、Review 管理、客户沟通 SOP。',
    docCount: 10,
    updatedAt: '22 小时前更新',
  },
}

const kbId = computed(() => route.params.id as string)
const kb = computed(() => kbMap[kbId.value] || { name: '未知', icon: 'library', description: '', docCount: 0, updatedAt: '' })

/* 硬数据：该库下的文档列表（后续接 API） */
const mockDocuments = [
  { id: 1, title: 'CPC 认证要求详解', type: 'PDF', size: '2.4 MB', status: '已审核' },
  { id: 2, title: 'FBA 头程运费对比表', type: 'XLSX', size: '156 KB', status: '待复核' },
  { id: 3, title: '亚马逊 A-to-Z 索赔处理流程', type: 'DOCX', size: '890 KB', status: '已审核' },
  { id: 4, title: 'PPC 广告竞价策略指南', type: 'PDF', size: '1.8 MB', status: '待复核' },
]
</script>

<template>
  <div class="kb-detail-page">
    <AppSidebar :collapsed="collapsed" @collapse="collapsed = !collapsed" />
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
            <span class="kb-meta">{{ kb.docCount }} 篇 · {{ kb.updatedAt }}</span>
          </div>
        </div>

        <!-- 操作栏 -->
        <div class="toolbar">
          <button class="btn-primary">
            <Icon name="plus" :size="16" />
            上传文档
          </button>
          <div class="toolbar-right">
            <input type="text" placeholder="搜索文档..." class="search-input" />
          </div>
        </div>

        <!-- 文档列表 -->
        <div class="doc-list">
          <div v-for="doc in mockDocuments" :key="doc.id" class="doc-item">
            <div class="doc-icon">
              <Icon name="library" :size="18" />
            </div>
            <div class="doc-info">
              <span class="doc-title">{{ doc.title }}</span>
              <span class="doc-meta">{{ doc.type }} · {{ doc.size }}</span>
            </div>
            <span class="doc-status" :class="doc.status === '待复核' ? 'pending' : ''">
              {{ doc.status }}
            </span>
          </div>
          <div v-if="mockDocuments.length === 0" class="empty-state">
            <Icon name="library" :size="36" />
            <p>暂无文档，点击上方按钮上传</p>
          </div>
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
