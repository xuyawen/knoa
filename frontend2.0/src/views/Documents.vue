<script setup lang="ts">
// 文档管理（对应截图 #3）：左侧子导航 + 工具条 + 筛选 + 文件表 + 分页。
// 界面壳阶段：静态示例数据，未接后端。批量/筛选/上传均为 UI 占位。
import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'

const tabs = [
  { key: 'mine', label: '我的文档' },
  { key: 'public', label: '公共文档' },
  { key: 'dept', label: '部门文档' },
  { key: 'archive', label: '文档归档' },
]
const activeTab = ref('mine')

const files = [
  { name: '2026 数据安全管理制度.pdf', type: 'PDF', time: '2026-07-20 09:42', owner: '张伟', status: 'done', scope: '部门可见' },
  { name: '产品使用手册 v3.2.docx', type: 'Word', time: '2026-07-20 09:15', owner: '李娜', status: 'done', scope: '公开可见' },
  { name: 'Q3 培训资料.pptx', type: 'PPT', time: '2026-07-19 17:30', owner: '王芳', status: 'parsing', scope: '仅本人可见' },
  { name: '客户FAQ清单.xlsx', type: 'Excel', time: '2026-07-19 14:08', owner: '陈强', status: 'failed', scope: '公司可见' },
  { name: '知识库建设方案.md', type: 'Markdown', time: '2026-07-18 11:22', owner: '赵敏', status: 'done', scope: '公开可见' },
  { name: '组织架构图.png', type: '图片', time: '2026-07-18 10:05', owner: '张伟', status: 'done', scope: '部门可见' },
  { name: '周会录音转写.txt', type: '文本', time: '2026-07-17 16:40', owner: '李娜', status: 'done', scope: '仅本人可见' },
]

const statusMap: Record<string, { label: string; cls: string }> = {
  done: { label: '解析完成', cls: 'badge-success' },
  parsing: { label: '解析中', cls: 'badge-warning' },
  failed: { label: '解析失败', cls: 'badge-danger' },
}

const selected = ref<Set<number>>(new Set())
function toggle(i: number) {
  const s = new Set(selected.value)
  s.has(i) ? s.delete(i) : s.add(i)
  selected.value = s
}
const page = ref(1)
const totalPages = 13
</script>

<template>
  <div class="page docs fade-up">
    <header class="page-head">
      <div class="flex items-center">
        <h1 class="page-title">文档管理</h1>
        <span class="todo-flag"><Icon name="sparkles" :size="12" />界面壳 · 示例数据</span>
      </div>
      <p class="page-sub">统一管理企业知识文档，支持多格式解析与权限分发</p>
    </header>

    <div class="docs-body">
      <!-- 左侧子导航 -->
      <aside class="docs-nav card">
        <div v-for="t in tabs" :key="t.key" class="nav-item" :class="{ active: activeTab === t.key }" @click="activeTab = t.key">
          <Icon :name="t.key === 'archive' ? 'folder' : 'doc'" :size="18" />
          <span>{{ t.label }}</span>
        </div>
        <div class="divider" style="margin: 8px 0" />
        <div class="nav-item"><Icon name="plus" :size="18" /><span>新建文件夹</span></div>
      </aside>

      <!-- 主区 -->
      <section class="docs-main card">
        <!-- 工具条 -->
        <div class="toolbar">
          <button class="btn btn-primary btn-sm"><Icon name="upload" :size="15" />批量上传</button>
          <button class="btn btn-ghost btn-sm"><Icon name="folder" :size="15" />新建文件夹</button>
          <div class="flex-1" />
          <button class="btn btn-ghost btn-sm"><Icon name="filter" :size="15" />筛选</button>
          <select class="select" style="width: 120px"><option>全部类型</option><option>PDF</option><option>Word</option><option>PPT</option><option>Excel</option></select>
          <select class="select" style="width: 120px"><option>解析状态</option><option>解析完成</option><option>解析中</option><option>解析失败</option></select>
          <select class="select" style="width: 120px"><option>权限范围</option><option>仅本人可见</option><option>部门可见</option><option>公司可见</option><option>公开可见</option></select>
        </div>

        <!-- 表 -->
        <table class="docs-table">
          <thead>
            <tr>
              <th style="width: 36px"><input type="checkbox" :checked="selected.size === files.length" /></th>
              <th>文件名称</th>
              <th>文件类型</th>
              <th>上传时间</th>
              <th>上传人</th>
              <th>解析状态</th>
              <th>权限范围</th>
              <th style="width: 120px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(f, i) in files" :key="i">
              <td><input type="checkbox" :checked="selected.has(i)" @change="toggle(i)" /></td>
              <td class="file-name"><Icon name="doc" :size="16" class="file-ic" />{{ f.name }}</td>
              <td>{{ f.type }}</td>
              <td class="text-secondary">{{ f.time }}</td>
              <td>{{ f.owner }}</td>
              <td><span class="badge" :class="statusMap[f.status].cls">{{ statusMap[f.status].label }}</span></td>
              <td class="text-secondary">{{ f.scope }}</td>
              <td>
                <div class="row-actions">
                  <button class="icon-btn sm" title="预览"><Icon name="eye" :size="15" /></button>
                  <button class="icon-btn sm" title="下载"><Icon name="download" :size="15" /></button>
                  <button class="icon-btn sm" title="更多"><Icon name="more" :size="15" /></button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 分页 -->
        <div class="pager">
          <span class="text-secondary text-sm">共 {{ totalPages * 10 }} 条 · 每页 10 条</span>
          <div class="pager-ctrl">
            <button class="btn btn-ghost btn-sm" :disabled="page === 1" @click="page > 1 && page--">上一页</button>
            <span class="page-now">{{ page }} / {{ totalPages }}</span>
            <button class="btn btn-ghost btn-sm" :disabled="page === totalPages" @click="page < totalPages && page++">下一页</button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.docs-body {
  display: grid;
  grid-template-columns: 210px 1fr;
  gap: 16px;
  align-items: start;
}
.docs-nav {
  padding: 12px;
  position: sticky;
  top: calc(var(--topbar-h) + 24px);
}
.docs-nav .nav-item { margin-bottom: 2px; }

.docs-main { padding: 0; overflow: hidden; }
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}
.toolbar .select { height: var(--btn-h-sm); }

.docs-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.docs-table th {
  text-align: left;
  padding: 11px 14px;
  color: var(--text-tertiary);
  font-weight: 500;
  background: var(--bg-surface-2);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.docs-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.docs-table tr:last-child td { border-bottom: none; }
.docs-table tbody tr:hover { background: var(--bg-hover); }
.file-name { display: flex; align-items: center; gap: 8px; max-width: 320px; }
.file-ic { color: var(--brand); flex-shrink: 0; }
.file-name { overflow: hidden; text-overflow: ellipsis; }
.row-actions { display: flex; gap: 2px; }
.icon-btn.sm { width: 30px; height: 30px; }

.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-top: 1px solid var(--border);
}
.pager-ctrl { display: flex; align-items: center; gap: 10px; }
.page-now { font-size: 13px; color: var(--text-secondary); }

@media (max-width: 920px) {
  .docs-body { grid-template-columns: 1fr; }
  .docs-nav { position: static; }
}
</style>
