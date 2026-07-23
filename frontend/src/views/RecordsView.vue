<script setup lang="ts">
// 检索记录 — 独立页面（遵循「一个页面一个文件」原则，从 Chat.vue 拆出）。
// 展示每次提问 + 回答的元数据快照：引用来源类型、反馈、时间，可展开看引用与摘要。
// 服务端分页（GET /api/records），不再一次性拉全部会话。
import { ref, computed, onMounted, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Pagination from '@/components/ui/Pagination.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useToastStore } from '@/stores/toast'
import { getRecords, getDocument } from '@/api'
import type { RecordItem, SourceItem, DocumentDetail } from '@/types/api'

const toast = useToastStore()

// ── 分页状态 ──
const records = ref<RecordItem[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const recordsLoading = ref(false)
const recordsFilter = ref<string>('all')
const expandedId = ref<string | null>(null)

// 文档详情弹框（引用源点击查看对应文档）
const docDetail = ref<DocumentDetail | null>(null)
const docDetailLoading = ref(false)
const detail = computed(() => docDetail.value!)

async function openDocDetail(s: SourceItem) {
  if (s.sourceType !== 'kb' || !s.kbId || !s.docId) {
    toast.warning('该来源不支持查看文档详情')
    return
  }
  docDetailLoading.value = true
  docDetail.value = null
  try {
    docDetail.value = await getDocument(s.kbId, s.docId)
  } catch (e: any) {
    toast.error(`加载文档失败：${e?.message || e}`)
  } finally {
    docDetailLoading.value = false
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function loadRecords() {
  recordsLoading.value = true
  try {
    const res = await getRecords({
      page: currentPage.value,
      size: pageSize.value,
      filter: recordsFilter.value === 'all' ? undefined : recordsFilter.value,
    })
    records.value = res.items
    total.value = res.total
  } catch (e: any) {
    toast.error(`加载检索记录失败：${e?.message || e}`)
    records.value = []
    total.value = 0
  } finally {
    recordsLoading.value = false
  }
}

// 切换过滤条件时回到第一页
watch(recordsFilter, () => {
  currentPage.value = 1
  loadRecords()
})

// 总页数守卫：切换 pageSize 后如果超出则回弹
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
watch([total, pageSize], () => {
  if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
})

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

onMounted(loadRecords)
</script>

<template>
  <div class="secondary-page">
    <div class="card records-card">
      <div class="records-header">
        <div class="records-title-row">
          <h2 class="records-title">检索记录</h2>
          <span class="records-count">{{ total }} 条提问</span>
        </div>
        <div class="records-filters">
          <button
            v-for="f in [{value:'all',label:'全部'},{value:'kb',label:'知识库'},{value:'web',label:'联网'},{value:'graph',label:'图谱'}]"
            :key="f.value"
            class="seg-btn"
            :class="{ active: recordsFilter === f.value }"
            @click="recordsFilter = f.value"
          >{{ f.label }}</button>
        </div>
      </div>

      <div v-if="recordsLoading" class="records-loading">
        <span class="dot" /><span class="dot" /><span class="dot" />
      </div>

      <div v-else-if="!records.length" class="records-empty">
        <Icon name="search" :size="32" />
        <p>暂无检索记录</p>
        <p class="records-empty-hint">去「对话」里问几个问题，这里就会展示每次检索的详情</p>
      </div>

      <template v-else>
        <div class="records-list">
          <div
            v-for="r in records"
            :key="r.id"
            class="record-card"
            :class="{ expanded: expandedId === r.id }"
          >
            <div class="record-card-head" @click="toggleExpand(r.id)">
              <div class="record-q">
                <Icon name="chat" :size="14" />
                <span class="record-q-text">{{ r.question }}</span>
              </div>
              <div class="record-card-meta">
                <div class="record-sources-badges">
                  <span v-if="r.kbCount > 0" class="src-badge kb">KB {{ r.kbCount }}</span>
                  <span v-if="r.webCount > 0" class="src-badge web">Web {{ r.webCount }}</span>
                  <span v-if="r.graphCount > 0" class="src-badge graph">图谱 {{ r.graphCount }}</span>
                  <span v-if="r.sourceCount === 0" class="src-badge none">无来源</span>
                </div>
                <span class="record-time">{{ r.createdAt?.slice(5, 10) || '' }}</span>
                <Icon :name="expandedId === r.id ? 'arrow-up' : 'chevron-down'" :size="14" />
              </div>
            </div>

            <div v-if="expandedId === r.id" class="record-card-body">
              <div class="record-session-tag">
                <Icon name="folder" :size="12" />
                {{ r.sessionTitle }}
              </div>

              <div v-if="r.sources?.length" class="record-sources-list">
                <div v-for="(s, si) in r.sources" :key="si" class="record-source-item" @click.stop="openDocDetail(s)">
                  <Icon :name="s.sourceType === 'kb' ? 'file-text' : s.sourceType === 'web' ? 'globe' : 'link'" :size="13" />
                  <span class="record-source-title">{{ s.title || '（未命名）' }}</span>
                  <span class="record-source-type">{{ s.sourceType === 'kb' ? '知识库' : s.sourceType === 'web' ? '联网' : '图谱' }}</span>
                </div>
              </div>
              <div v-else class="record-no-sources">本次回答未引用任何来源</div>

              <div class="record-answer-preview">
                <div class="record-answer-label">回答摘要</div>
                <p class="record-answer-text">{{ r.answer.slice(0, 300) }}{{ r.answer.length > 300 ? '...' : '' }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 分页条 -->
        <Pagination
          v-if="total > 0"
          v-model:page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          @update:page="loadRecords()"
          @update:page-size="loadRecords()"
        />
      </template>
    </div>
  </div>

  <!-- 文档详情弹框 -->
  <AppModal
    :show="!!docDetail"
    :title="docDetail?.title || '文档详情'"
    wide
    @close="docDetail = null"
  >
    <template v-if="docDetailLoading" #default>
      <div class="doc-detail-loading">
        <span class="dot" /><span class="dot" /><span class="dot" />
      </div>
    </template>
    <template v-else-if="docDetail" #default>
      <div class="doc-detail">
        <div class="doc-meta-grid">
          <div class="doc-meta-item">
            <span class="doc-meta-label">类型</span>
            <span class="doc-meta-value">{{ detail.type || '—' }}</span>
          </div>
          <div class="doc-meta-item">
            <span class="doc-meta-label">状态</span>
            <span class="doc-meta-value" :class="'status-' + (detail.status || '')">{{ detail.status || '—' }}</span>
          </div>
          <div class="doc-meta-item">
            <span class="doc-meta-label">更新时间</span>
            <span class="doc-meta-value mono">{{ detail.updatedAt?.slice(0, 16) || '—' }}</span>
          </div>
        </div>
        <div v-if="detail.originalFilename" class="doc-file-info">
          <Icon name="file-text" :size="14" />
          <span>{{ detail.originalFilename }}</span>
          <span v-if="detail.fileSize" class="doc-file-size">({{ formatSize(detail.fileSize) }})</span>
        </div>
        <div v-if="detail.reviewedAt" class="doc-review-info">
          审核于 {{ detail.reviewedAt.slice(0, 16) }}
          <span v-if="detail.reviewedBy"> · {{ detail.reviewedBy }}</span>
        </div>
        <div class="doc-content">
          <div class="doc-content-label">文档内容</div>
          <pre class="doc-content-body">{{ detail.contentMd }}</pre>
        </div>
      </div>
    </template>
  </AppModal>
</template>

<style scoped>
/* ============ 检索记录 ============ */
.records-card {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02);
}
.records-header { margin-bottom: 20px; padding: 18px 20px 0; }
.records-title-row { display: flex; align-items: baseline; gap: 12px; margin-bottom: 14px; }
.records-title { font-size: 18px; font-weight: 700; color: var(--text-primary); margin: 0; }
.records-count { font-size: 13px; color: var(--text-tertiary); }
.records-filters { display: flex; gap: 6px; }
.records-filters .seg-btn {
  padding: 5px 14px;
  font-size: 12.5px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.records-filters .seg-btn:hover { border-color: var(--brand); color: var(--brand); }
.records-filters .seg-btn.active { background: var(--brand); border-color: var(--brand); color: #fff; }

.records-loading { display: flex; justify-content: center; padding: 48px 20px; gap: 6px; }
.records-loading .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--brand); animation: bounce 1.4s infinite ease-in-out both; }
.records-loading .dot:nth-child(1) { animation-delay: -0.32s; }
.records-loading .dot:nth-child(2) { animation-delay: -0.16s; }

.records-empty { text-align: center; padding: 48px 20px; color: var(--text-tertiary); }
.records-empty p { margin: 8px 0 0; font-size: 14px; }
.records-empty-hint { font-size: 12.5px !important; color: var(--text-tertiary) !important; }

.records-list { display: flex; flex-direction: column; gap: 12px; padding: 0 20px; }

.record-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02);
  overflow: hidden;
  transition: border-color var(--dur-fast) var(--ease-out),
    box-shadow var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out);
}
.record-card:hover {
  border-color: var(--brand-soft);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.03);
  transform: translateY(-1px);
}
.record-card.expanded { border-color: var(--brand); box-shadow: 0 4px 14px rgba(9, 88, 217, 0.08); }

.record-card-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 16px 18px; cursor: pointer;
  user-select: none;
}
.record-card-head:hover .record-q-text { color: var(--brand); }
.record-q { display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1; }
.record-q-text { font-size: 13.5px; font-weight: 500; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: color var(--dur-fast) var(--ease-out); }

.record-card-meta { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.record-sources-badges { display: flex; gap: 4px; }
.src-badge {
  padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; line-height: 1.6;
}
.src-badge.kb { background: #eef7ff; color: #0958d9; }
.src-badge.web { background: #f0fdf4; color: #15803d; }
.src-badge.graph { background: #faf5ff; color: #7c3aed; }
.src-badge.none { background: var(--bg-subtle); color: var(--text-tertiary); }
.record-time { font-size: 12px; color: var(--text-tertiary); font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', Consolas, monospace); }

.record-card-body { padding: 0 18px 18px; border-top: 1px solid var(--border-deep); animation: fadeIn 0.2s ease-out; }
.record-session-tag { display: inline-flex; align-items: center; gap: 5px; padding: 6px 10px; margin-top: 12px; background: var(--bg-subtle); border-radius: var(--radius-sm); font-size: 12px; color: var(--text-secondary); }

.record-sources-list { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
.record-source-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 10px;
  border-radius: var(--radius-md); background: var(--bg-subtle);
  font-size: 12.5px; color: var(--text-secondary); cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out);
}
.record-source-item:hover { background: var(--brand-soft); color: var(--brand); }
.record-source-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.record-source-type { flex-shrink: 0; font-size: 11px; color: var(--text-tertiary); }

.record-no-sources { margin-top: 12px; font-size: 12.5px; color: var(--text-tertiary); font-style: italic; }

.record-answer-preview { margin-top: 14px; }
.record-answer-label { font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; }
.record-answer-text { margin: 0; font-size: 13px; line-height: 1.7; color: var(--text-primary); white-space: pre-wrap; word-break: break-word; }

/* ============ 文档详情弹框 ============ */
.doc-detail-loading {
  display: flex;
  gap: 6px;
  padding: 40px 0;
  justify-content: center;
}
.doc-detail-loading .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--text-tertiary);
  animation: blink 1.3s infinite ease-in-out;
}
.doc-detail-loading .dot:nth-child(2) { animation-delay: 0.18s; }
.doc-detail-loading .dot:nth-child(3) { animation-delay: 0.36s; }

.doc-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.doc-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 20px;
}
.doc-meta-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.doc-meta-label {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.doc-meta-value {
  font-size: 13.5px;
  color: var(--text-primary);
  font-weight: 500;
}
.mono { font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', Consolas, monospace); }
.doc-meta-value.status-已审核 { color: var(--success); }
.doc-meta-value.status-待复核 { color: var(--warning); }
.doc-meta-value.status-已拒绝 { color: var(--danger); }

.doc-file-info {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
}
.doc-file-size {
  color: var(--text-tertiary);
  font-size: 12px;
}
.doc-review-info {
  font-size: 12.5px;
  color: var(--text-tertiary);
}

.doc-content {
  border-top: 1px solid var(--border);
  padding-top: 14px;
}
.doc-content-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.doc-content-body {
  margin: 0;
  padding: 14px 16px;
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.75;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

@keyframes blink { 0%, 80%, 100% { opacity: 0.25; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-3px); } }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
