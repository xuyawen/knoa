<script setup lang="ts">
// 文档详情弹框（问答溯源点击引用卡片打开），从 Chat.vue 拆出。
import { computed, nextTick, ref, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import type { DocumentDetail } from '@/types/api'

const props = defineProps<{
  doc: DocumentDetail | null
  loading: boolean
  /** 引用来源的片段：在全文中高亮并滚动到可见区 */
  snippet?: string
}>()

defineEmits<{ (e: 'close'): void }>()

// 模板里 doc 已由 v-else-if 保证非空，收窄一层方便直接引用
const detail = () => props.doc!

const bodyRef = ref<HTMLElement | null>(null)

/** 格式化文件大小。 */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function escapeReg(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 引用片段在入库时被截断并把换行替换为空格，无法直接 indexOf：
// 取前 24 字按空白拆词，用「容空白」正则在全文中定位，命中包 <mark>。
const highlightedContent = computed(() => {
  const text = props.doc?.contentMd || ''
  const raw = (props.snippet || '').replace(/\.{3}$/, '').trim()
  if (!text || raw.length < 12) return escapeHtml(text)
  const pattern = raw.slice(0, 24).split(/\s+/).filter(Boolean).map(escapeReg).join('\\s+')
  const m = new RegExp(pattern).exec(text)
  if (!m) return escapeHtml(text)
  return (
    escapeHtml(text.slice(0, m.index)) +
    '<mark>' + escapeHtml(text.slice(m.index, m.index + m[0].length)) + '</mark>' +
    escapeHtml(text.slice(m.index + m[0].length))
  )
})

// 文档加载完成后把高亮片段滚到可见区
watch(() => props.doc, async () => {
  await nextTick()
  bodyRef.value?.querySelector('mark')?.scrollIntoView({ block: 'center' })
})
</script>

<template>
  <AppModal
    :show="!!doc"
    :title="doc?.title || '文档详情'"
    wide
    @close="$emit('close')"
  >
    <template v-if="loading" #default>
      <div class="doc-detail-loading">
        <span class="dot" /><span class="dot" /><span class="dot" />
      </div>
    </template>
    <template v-else-if="doc" #default>
      <div class="doc-detail">
        <div class="doc-meta-grid">
          <div class="doc-meta-item">
            <span class="doc-meta-label">类型</span>
            <span class="doc-meta-value">{{ detail().type || '—' }}</span>
          </div>
          <div class="doc-meta-item">
            <span class="doc-meta-label">状态</span>
            <span class="doc-meta-value" :class="'status-' + (detail().status || '')">{{ detail().status || '—' }}</span>
          </div>
          <div class="doc-meta-item">
            <span class="doc-meta-label">更新时间</span>
            <span class="doc-meta-value mono">{{ detail().updatedAt?.slice(0, 16) || '—' }}</span>
          </div>
        </div>
        <div v-if="detail().originalFilename" class="doc-file-info">
          <Icon name="file-text" :size="14" />
          <span>{{ detail().originalFilename }}</span>
          <span v-if="detail().fileSize" class="doc-file-size">({{ formatSize(detail().fileSize!) }})</span>
        </div>
        <div v-if="detail().reviewedAt" class="doc-review-info">
          审核于 {{ detail().reviewedAt!.slice(0, 16) }}
          <span v-if="detail().reviewedBy"> · {{ detail().reviewedBy }}</span>
        </div>
        <div class="doc-content">
          <div class="doc-content-label">文档内容</div>
          <pre ref="bodyRef" class="doc-content-body" v-html="highlightedContent"></pre>
        </div>
      </div>
    </template>
  </AppModal>
</template>

<style scoped>
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
@keyframes blink { 0%, 80%, 100% { opacity: 0.25; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-3px); } }

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
.doc-content-body :deep(mark) {
  background: #fff1a8;
  color: inherit;
  border-radius: 3px;
  padding: 1px 2px;
  box-shadow: 0 0 0 1px #f5d943;
}
</style>
