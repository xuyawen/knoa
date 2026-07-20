<script setup lang="ts">
// 文档管理 — 按 640(3).png 截图 1:1 还原。
defineProps<{ activeTab?: number }>()

import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'

const viewMode = ref<'list' | 'grid'>('list')
const searchQuery = ref('')

const files = [
  { name: '2024年产品需求文档.pdf', type: 'PDF', icon: 'pdf', color: '#EF4444', time: '2024-05-20 14:30:22', user: '张三', status: '解析完成', statusType: 'success', scope: '仅本人可见' },
  { name: '企业知识库使用手册.docx', type: 'DOCX', icon: 'doc', color: '#3B82F6', time: '2024-05-20 11:20:15', user: '李四', status: '解析完成', statusType: 'success', scope: '部门可见' },
  { name: 'Q2市场数据分析报告.xlsx', type: 'XLSX', icon: 'excel', color: '#10B981', time: '2024-05-19 16:45:30', user: '王五', status: '解析完成', statusType: 'success', scope: '部门可见' },
  { name: '新员工入职培训.pptx', type: 'PPTX', icon: 'pptx', color: '#F59E0B', time: '2024-05-19 09:15:45', user: '赵六', status: '解析中', statusType: 'warning', scope: '公司可见' },
  { name: '信息安全管理制度.pdf', type: 'PDF', icon: 'pdf', color: '#EF4444', time: '2024-05-18 17:20:33', user: '张三', status: '解析完成', statusType: 'success', scope: '公司可见' },
  { name: '项目管理流程规范.docx', type: 'DOCX', icon: 'doc', color: '#3B82F6', time: '2024-05-18 10:05:12', user: '李四', status: '解析失败', statusType: 'danger', scope: '部门可见' },
  { name: '客户服务协议模版.pdf', type: 'PDF', icon: 'pdf', color: '#EF4444', time: '2024-05-17 15:30:25', user: '王五', status: '解析完成', statusType: 'success', scope: '公开可见' },
  { name: '年度预算计划表.xlsx', type: 'XLSX', icon: 'excel', color: '#10B981', time: '2024-05-17 11:10:08', user: '赵六', status: '解析完成', statusType: 'success', scope: '仅本人可见' },
]

function clearSearch() {
  searchQuery.value = ''
}
</script>

<template>
  <div class="docs-page">
    <!-- 页面标题 -->
    <h2 class="page-title">文档管理</h2>

    <!-- ====== 工具栏 ====== -->
    <div class="toolbar card">
      <div class="toolbar-left">
        <!-- 搜索框 -->
        <div class="search-box">
          <Icon name="search" :size="14" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索文档名称、内容、上传人等" class="search-input" />
          <button v-if="searchQuery" class="search-clear" @click="clearSearch">
            <Icon name="close" :size="12" />
          </button>
        </div>

        <!-- 操作按钮组 -->
        <button class="btn btn-primary btn-sm">
          <Icon name="upload" :size="13" /> 批量上传
        </button>
        <button class="btn btn-ghost btn-sm">
          <Icon name="folder" :size="13" /> 新建文件夹
        </button>

        <!-- 筛选下拉 -->
        <div class="toolbar-select">
          <span>筛选</span> <Icon name="chevron-down" :size="11" />
        </div>
        <div class="toolbar-select">
          <span>文件类型</span> <Icon name="chevron-down" :size="11" />
        </div>
        <div class="toolbar-select">
          <span>解析状态</span> <Icon name="chevron-down" :size="11" />
        </div>
        <div class="toolbar-select">
          <span>权限范围</span> <Icon name="chevron-down" :size="11" />
        </div>
        <div class="toolbar-select">
          <span>更多筛选</span> <Icon name="chevron-down" :size="11" />
        </div>

        <!-- 刷新 -->
        <button class="icon-btn" title="刷新"><Icon name="refresh" :size="15" /></button>
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

    <!-- ====== 文件表格 ====== -->
    <div class="file-table-wrap card">
      <table class="file-table">
        <thead>
          <tr>
            <th class="col-check"><input type="checkbox" /></th>
            <th>文档名称</th>
            <th>文件类型</th>
            <th>上传时间 <Icon name="chevron-down" :size="11" style="vertical-align:middle;opacity:.5"/></th>
            <th>上传人</th>
            <th>文档解析状态</th>
            <th>权限范围</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(f, i) in files" :key="i">
            <td class="col-check"><input type="checkbox" /></td>
            <td>
              <div class="file-name-cell">
                <span class="file-icon-sm" :style="{ background: f.color + '18', color: f.color }">
                  <Icon :name="f.icon === 'pdf' ? 'pdf' : f.icon === 'excel' ? 'excel' : f.icon === 'pptx' ? 'pptx' : 'doc'" :size="15" />
                </span>
                <span class="file-name">{{ f.name }}</span>
              </div>
            </td>
            <td><span class="type-text">{{ f.type }}</span></td>
            <td class="col-time">{{ f.time }}</td>
            <td>{{ f.user }}</td>
            <td>
              <span class="status-badge" :class="f.statusType">{{ f.status }}</span>
            </td>
            <td><span class="scope-badge">{{ f.scope }}</span></td>
            <td>
              <div class="row-actions">
                <button class="action-btn" title="预览"><Icon name="eye" :size="15" /></button>
                <button class="action-btn" title="下载"><Icon name="download" :size="15" /></button>
                <button class="action-btn" title="更多"><Icon name="more" :size="16" /></button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ====== 分页 ====== -->
    <div class="pagination-bar card">
      <div class="page-info">共 128 条</div>
      <div class="page-size">
        <select class="select page-size-select">
          <option>10条/页</option>
          <option>20条/页</option>
          <option>50条/页</option>
        </select>
      </div>
      <div class="page-numbers">
        <button class="pg active">1</button>
        <button class="pg">2</button>
        <button class="pg">3</button>
        <button class="pg">4</button>
        <button class="pg">5</button>
        <span class="pg-dots">...</span>
        <button class="pg">13</button>
        <button class="pg-arrow">&gt;</button>
      </div>
      <div class="page-jump">
        跳至 <input type="text" value="1" class="jump-input" /> 页
      </div>
    </div>
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

/* ---- 工具栏 ---- */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  gap: 12px;
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
  width: 260px;
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

/* 工具栏下拉模拟 */
.toolbar-select {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  white-space: nowrap;
  background: var(--bg-surface);
  transition: all var(--dur-fast);
}
.toolbar-select:hover {
  border-color: var(--brand);
  color: var(--text-primary);
}

/* 视图切换 */
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
.col-check { width: 38px; text-align: center; }
.col-check input[type='checkbox'] { accent-color: var(--brand); width: 15px; height: 15px; }

/* 文件名单元格 */
.file-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
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
}
.type-text { color: var(--text-secondary); }
.col-time { color: var(--text-tertiary); white-space: nowrap; }

/* 状态标签 */
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 500;
}
.status-badge.success { background: #D1FAE5; color: #065F46; }
.status-badge.warning { background: #FEF3C7; color: #92400E; }
.status-badge.danger { background: #FEE2E2; color: #991B1B; }

/* 权限范围标签 */
.scope-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  color: var(--brand);
  background: var(--brand-soft);
}

/* 行操作按钮 */
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
}
.page-numbers {
  display: flex;
  align-items: center;
  gap: 4px;
}
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
.pg:hover { border-color: var(--brand); color: var(--brand); }
.pg.active { background: var(--brand); color: #fff; border-color: var(--brand); }
.pg-dots { color: var(--text-tertiary); padding: 0 4px; }
.pg-arrow { font-family: inherit; }
.jump-input {
  width: 40px;
  height: 30px;
  text-align: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
}
.jump-input:focus { outline: none; border-color: var(--brand); }
</style>
