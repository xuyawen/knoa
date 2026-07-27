<script setup lang="ts">
// 文档预览弹窗（含右侧 AI 辅助审核面板），从 DocumentLibrary.vue 拆出。
// AI 审核状态归本组件所有：切换预览文档时自动清空上次结论。
import { ref, watch } from 'vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { aiReviewDocument } from '@/api'
import type { DocumentDetail, AIReview } from '@/types/api'

const props = defineProps<{
  doc: DocumentDetail | null
  loading: boolean
  kbId: string
}>()

defineEmits<{ (e: 'close'): void }>()

const toast = useToastStore()

const aiReview = ref<AIReview | null>(null)
const aiReviewLoading = ref(false)

// 换文档预览时清空上次 AI 审核结论
watch(
  () => props.doc?.id,
  () => {
    aiReview.value = null
  },
)

async function onAiReview() {
  if (!props.kbId || !props.doc) return
  aiReviewLoading.value = true
  aiReview.value = null
  try {
    aiReview.value = await aiReviewDocument(props.kbId, props.doc.id)
  } catch (e: unknown) {
    toast.error(`AI 审核失败：${errMsg(e)}`)
  } finally {
    aiReviewLoading.value = false
  }
}

/** 状态徽标配色（与列表页一致）。 */
function statusType(s: string): 'success' | 'warning' | 'danger' {
  if (s === '已审核') return 'success'
  if (s === '待复核' || s === '解析中') return 'warning'
  return 'danger'
}

function fmtTime(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
</script>

<template>
  <AppModal :show="!!doc || loading" title="文档预览" wide @close="$emit('close')">
    <div v-if="loading" class="modal-hint">加载中…</div>
    <template v-else-if="doc">
      <div class="preview-toolbar">
        <button class="btn btn-primary btn-sm" :disabled="aiReviewLoading" @click="onAiReview">
          <span v-if="aiReviewLoading" class="spinner sm"></span>
          {{ aiReviewLoading ? '分析中…' : (aiReview ? '重新审核' : 'AI 审核') }}
        </button>
      </div>
      <div class="preview-split">
        <!-- 左：文档内容 -->
        <div class="preview-left">
          <div class="preview-meta">
            <span class="type-text">{{ doc.type }}</span>
            <span class="col-time">{{ fmtTime(doc.updatedAt) }}</span>
            <span class="status-badge mini" :class="statusType(doc.status)">{{ doc.status }}</span>
          </div>
          <pre class="preview-body">{{ doc.contentMd || '（无内容）' }}</pre>
        </div>
        <!-- 右：AI 审核建议 -->
        <aside class="preview-right">
          <div class="ai-panel-head">AI 辅助审核</div>
          <div v-if="aiReviewLoading" class="ai-loading">
            <span class="spinner"></span>
            正在调用大模型分析文档，请稍候…
          </div>
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
          <div v-else class="ai-empty">
            点击左上角「AI 审核」按钮，调用大模型分析该文档并给出建议。
          </div>
        </aside>
      </div>
    </template>
  </AppModal>
</template>

<style scoped>
.modal-hint { color: var(--text-tertiary); text-align: center; padding: 20px 0; }
.type-text { color: var(--text-secondary); font-weight: 500; }
.col-time { color: var(--text-tertiary); white-space: nowrap; }
.status-badge {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 600;
}
.status-badge.success { background: var(--success-soft); color: var(--success); }
.status-badge.warning { background: var(--warning-soft); color: var(--warning); }
.status-badge.danger { background: var(--danger-soft); color: var(--danger); }
.status-badge.mini { padding: 1px 8px; font-size: 11px; }

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border);
  border-top-color: var(--brand);
  border-radius: 50%;
  animation: ai-spin 0.7s linear infinite;
}
.spinner.sm {
  width: 13px;
  height: 13px;
  border-width: 2px;
}
@keyframes ai-spin { to { transform: rotate(360deg); } }

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
/* 预览弹窗顶部工具条（AI 审核触发） */
.preview-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}
/* 预览 + AI 审核左右分栏 */
.preview-split {
  display: flex;
  gap: 16px;
  align-items: stretch;
}
.preview-left {
  flex: 1 1 auto;
  min-width: 0;
}
.preview-right {
  flex: 0 0 268px;
  border-left: 1px solid var(--border);
  padding-left: 16px;
  max-height: 58vh;
  overflow-y: auto;
}
.ai-panel-head {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
}
.ai-empty {
  font-size: 13px;
  color: var(--text-tertiary);
  line-height: 1.6;
  padding: 12px 0;
}
.ai-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 24px 0;
  color: var(--text-secondary);
  font-size: 13px;
}
.ai-verdict {
  display: inline-block;
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 10px;
}
.ai-verdict.approve { background: var(--success-soft); color: var(--success); }
.ai-verdict.reject { background: var(--danger-soft); color: var(--danger); }
.ai-verdict.manual_review, .ai-verdict.manual { background: var(--warning-soft); color: var(--warning); }
.ai-summary { margin: 0 0 14px; color: var(--text-secondary); line-height: 1.6; }
.ai-section h4 { font-size: 13px; color: var(--text-primary); margin: 14px 0 6px; }
.ai-list { margin: 0; padding-left: 18px; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.ai-list li { margin-bottom: 8px; }
.ai-sim { color: var(--brand); font-weight: 600; margin-right: 8px; }
.ai-doc { font-weight: 500; color: var(--text-primary); }
.ai-snippet { margin: 4px 0 0; color: var(--text-tertiary); font-size: 12px; }
</style>
