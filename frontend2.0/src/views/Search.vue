<script setup lang="ts">
// 智能搜索 — 按 640(4).png 截图 1:1 还原。
defineProps<{ activeTab?: number }>()

import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'

const searchQuery = ref('企业数据安全管理规范')
const viewMode = ref<'list' | 'grid'>('list')

const results = [
  {
    icon: 'doc', iconBg: '#E6F0FF', iconColor: '#3B82F6', iconLetter: 'W',
    title: '企业数据安全管理规范 v2.1',
    summary: '…为加强企业<strong>数据安全</strong>管理，规范数据处理活动，保障数据安全，特制定本规范。本规范适用于公司及各子公司全体员工，涵盖数据收集、存储、使用、传输、销毁全生命周期需要…',
    source: '安全管理 > 数据安全',
    time: '2024-05-20 10:30',
    scope: '仅企业内部可见',
  },
  {
    icon: 'pdf', iconBg: '#FEE2E2', iconColor: '#EF4444', iconLetter: '',
    title: '数据安全分级分类实施指南',
    summary: '…本指南围绕<strong>数据安全</strong>分级分类方法展开，帮助企业识别和划分数据重要性等级，明确不同级别数据的安全保护措施和管理要求，提升整体<strong>数据安全</strong>防护能力…',
    source: '安全管理 > 实施指南',
    time: '2024-04-28 15:45',
    scope: '仅企业内部可见',
  },
  {
    icon: 'excel', iconBg: '#D1FAE5', iconColor: '#10B981', iconLetter: '',
    title: '数据安全检查清单（2024版）',
    summary: '…本清单用于检查企业<strong>数据安全</strong>管理的合规性，内容包括数据权限管理、数据脱敏、日志审计、应急响应等关键控制点，确保<strong>数据安全</strong>管理措施有效落地…',
    source: '安全管理 > 检查清单',
    time: '2024-05-15 09:20',
    scope: '部分部门可见',
  },
  {
    icon: 'pptx', iconBg: '#FEF3C7', iconColor: '#F59E0B', iconLetter: '',
    title: '数据安全培训课件',
    summary: '…本课件适用于员工<strong>数据安全</strong>意识培训，内容涵盖<strong>数据安全</strong>法规、公司政策、案例分析及最佳实践，帮助员工理解并遵守<strong>数据安全</strong>管理要求…',
    source: '培训资料 > 安全培训',
    time: '2024-03-30 11:10',
    scope: '仅企业内部可见',
  },
]

function clearSearch() { searchQuery.value = '' }
function clearFilters() {}
</script>

<template>
  <div class="search-page">
    <!-- 页面标题 -->
    <h2 class="page-title">智能搜索</h2>

    <!-- ====== 搜索栏 ====== -->
    <div class="search-bar-row card">
      <div class="search-input-wrap">
        <Icon name="search" :size="17" class="sb-icon" />
        <input v-model="searchQuery" type="text" placeholder="搜索文档名称、内容..." class="sb-input" />
        <button v-if="searchQuery" class="sb-clear" @click="clearSearch">
          <Icon name="close" :size="13" />
        </button>
      </div>
      <button class="btn btn-primary sb-btn">搜索</button>

      <a href="#" class="adv-search-link">高级搜索 <Icon name="chevron-down" :size="11" /></a>
    </div>

    <!-- ====== 筛选行 ====== -->
    <div class="filter-row">
      <div class="filter-item">
        <span class="filter-label">文件类型：</span>
        <div class="filter-dropdown">全部类别 <Icon name="chevron-down" :size="11" /></div>
      </div>
      <div class="filter-item">
        <span class="filter-label">更新时间：</span>
        <div class="filter-dropdown">全部时间 <Icon name="chevron-down" :size="11" /></div>
      </div>
      <div class="filter-item">
        <span class="filter-label">文档分类：</span>
        <div class="filter-dropdown">全部分类 <Icon name="chevron-down" :size="11" /></div>
      </div>
      <div class="filter-item">
        <span class="filter-label">权限范围：</span>
        <div class="filter-dropdown">全部权限 <Icon name="chevron-down" :size="11" /></div>
      </div>
      <button class="clear-filters" @click="clearFilters">
        <Icon name="refresh" :size="12" /> 清空
      </button>
      <button class="expand-filter">
        展开 <Icon name="chevron-down" :size="11" />
      </button>
    </div>

    <!-- ====== 结果统计 + 排序 ====== -->
    <div class="result-header">
      <span class="result-count">找到约 <strong>128</strong> 条结果 (用时 0.23 秒)</span>
      <div class="result-actions">
        <div class="sort-select">相关度排序 <Icon name="chevron-down" :size="11" /></div>
        <button class="view-toggle" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'"><Icon name="listview" :size="16" /></button>
        <button class="view-toggle" :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'"><Icon name="gridview" :size="16" /></button>
      </div>
    </div>

    <!-- ====== 搜索结果卡片列表 ====== -->
    <div class="result-list">
      <div v-for="(r, i) in results" :key="i" class="result-card card">
        <div class="rc-head">
          <div class="rc-icon" :style="{ background: r.iconBg }">
            <span v-if="r.iconLetter" class="rc-letter" :style="{ color: r.iconColor }">{{ r.iconLetter }}</span>
            <Icon v-else :name="r.icon === 'pdf' ? 'pdf' : r.icon === 'excel' ? 'excel' : r.icon === 'pptx' ? 'pptx' : 'doc'" :size="22" :style="{ color: r.iconColor }" />
          </div>
          <h3 class="rc-title">{{ r.title }}</h3>
        </div>
        <p class="rc-summary" v-html="r.summary"></p>
        <div class="rc-meta">
          <span class="meta-item"><Icon name="folder" :size="12" /> 来源：{{ r.source }}</span>
          <span class="meta-item"><Icon name="clock" :size="12" /> 更新时间：{{ r.time }}</span>
          <span class="meta-item meta-scope"><Icon name="shield" :size="12" /> 权限：{{ r.scope }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.search-page {
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
}
.sb-clear:hover { background: var(--bg-hover); }
.sb-btn { height: 42px; padding: 0 28px; font-size: 14px; }

.adv-search-link {
  margin-left: auto;
  font-size: 13px;
  color: var(--text-secondary);
  text-decoration: none;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.adv-search-link:hover { color: var(--brand); }

/* ---- 筛选行 ---- */
.filter-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 8px 0;
}
.filter-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.filter-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.filter-dropdown {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
  background: var(--bg-surface);
  white-space: nowrap;
}
.filter-dropdown:hover { border-color: var(--brand); }
.clear-filters, .expand-filter {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--brand);
  cursor: pointer;
  font-family: inherit;
}
.clear-filters:hover, .expand-filter:hover { opacity: 0.75; }

/* ---- 结果头 ---- */
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0 8px;
}
.result-count {
  font-size: 13px;
  color: var(--text-secondary);
}
.result-count strong { color: var(--text-primary); }
.result-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sort-select {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  background: var(--bg-surface);
}

.view-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
}
.view-toggle:hover { background: var(--bg-hover); color: var(--text-secondary); }
.view-toggle.active { background: var(--brand); color: #fff; border-color: var(--brand); }

/* ---- 结果卡片 ---- */
.result-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.result-card {
  padding: 18px 20px;
  transition: box-shadow var(--dur-fast), transform var(--dur-fast);
}
.result-card:hover {
  box-shadow: var(--shadow-float);
  transform: translateY(-1px);
}

.rc-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.rc-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.rc-letter {
  font-size: 18px;
  font-weight: 800;
  font-family: var(--font-display);
}
.rc-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.35;
}

.rc-summary {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
  margin: 0 0 12px;
}
/* 高亮关键词 */
.rc-summary :deep(strong) {
  background: linear-gradient(120deg, rgba(245, 158, 11, 0.25), rgba(245, 158, 11, 0.15));
  color: #92400E;
  padding: 0 2px;
  border-radius: 2px;
  font-weight: 600;
}

.rc-meta {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}
.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.meta-scope { color: var(--brand); font-weight: 500; }

</style>
