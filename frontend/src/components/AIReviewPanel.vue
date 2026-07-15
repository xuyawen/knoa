<script setup lang="ts">
import Icon from '@/components/Icon.vue'
import type { AIReview } from '@/types/api'

defineProps<{
  review: AIReview
  loading?: boolean
}>()

function verdictLabel(v: string): string {
  const map: Record<string, string> = {
    approve: '建议通过',
    reject: '建议驳回',
    manual_review: '需人工复核',
  }
  return map[v] || v
}

const verdictIcon: Record<string, string> = {
  approve: 'check',
  reject: 'thumb-down',
  manual_review: 'alert-circle',
}
</script>

<template>
  <div class="ai-review-panel" :class="{ loading }">
    <div class="review-header">
      <span class="review-header-icon"><Icon name="sparkle" :size="15" /></span>
      <span>AI 审核建议</span>
      <span v-if="loading" class="review-loading-dot" />
    </div>

    <div class="verdict-badge" :class="review.verdict">
      <Icon :name="verdictIcon[review.verdict] || 'sparkle'" :size="13" />
      {{ verdictLabel(review.verdict) }}
    </div>

    <p class="review-summary">{{ review.summary }}</p>

    <div v-if="review.duplicates.length" class="review-section">
      <h4 class="review-title danger"><Icon name="copy" :size="13" /> 重复风险</h4>
      <ul class="review-list">
        <li v-for="(d, i) in review.duplicates" :key="i">{{ d }}</li>
      </ul>
    </div>

    <div v-if="review.outdatedFindings.length" class="review-section">
      <h4 class="review-title warning"><Icon name="clock" :size="13" /> 过时信息</h4>
      <ul class="review-list">
        <li v-for="(o, i) in review.outdatedFindings" :key="i">{{ o }}</li>
      </ul>
    </div>

    <div v-if="review.qualityNotes.length" class="review-section">
      <h4 class="review-title"><Icon name="check" :size="13" /> 质量建议</h4>
      <ul class="review-list">
        <li v-for="(q, i) in review.qualityNotes" :key="i">{{ q }}</li>
      </ul>
    </div>

    <div v-if="review.suggestedKb" class="review-section">
      <h4 class="review-title"><Icon name="library" :size="13" /> 建议归属</h4>
      <p class="review-note">该文档可能更适合：<strong>{{ review.suggestedKb }}</strong></p>
    </div>

    <div v-if="review.similarityFindings.length" class="review-section">
      <h4 class="review-title danger"><Icon name="graph" :size="13" /> 相似内容对比</h4>
      <div class="sim-detail">
        <div v-for="(f, i) in review.similarityFindings" :key="i" class="sim-card">
          <div class="sim-row">
            <span class="sim-doc">{{ f.docTitle }}</span>
            <span class="sim-score">相似度 {{ (f.similarity * 100).toFixed(0) }}%</span>
          </div>
          <pre class="sim-snippet">{{ f.snippet }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-review-panel {
  margin-top: 16px;
  padding: 16px 18px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  position: relative;
  overflow: hidden;
}
.ai-review-panel::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: linear-gradient(to bottom, var(--brand), var(--brand-hover));
  opacity: 0.7;
}

.review-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}
.review-header-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  background: var(--brand-soft);
  color: var(--brand);
}
.review-loading-dot {
  margin-left: auto;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--brand);
  animation: review-pulse 1s ease-in-out infinite;
}
@keyframes review-pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.1); }
}

.verdict-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 10px;
}
.verdict-badge.approve {
  background: #D1FAE5;
  color: #065F46;
}
.verdict-badge.reject {
  background: #FEE2E2;
  color: #991B1B;
}
.verdict-badge.manual_review {
  background: #FEF3C7;
  color: #92400E;
}

.review-summary {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
}

.review-section {
  margin-bottom: 14px;
}
.review-section:last-child {
  margin-bottom: 0;
}
.review-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 0 0 7px;
  color: var(--text-secondary);
}
.review-title.danger {
  color: var(--danger);
}
.review-title.warning {
  color: var(--warning);
}
.review-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.review-list li {
  position: relative;
  font-size: 13px;
  line-height: 1.55;
  color: var(--text-secondary);
  padding-left: 14px;
  margin-bottom: 5px;
}
.review-list li::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 8px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-placeholder);
}
.review-note {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.sim-detail {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sim-card {
  padding: 10px 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.sim-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.sim-doc {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.sim-score {
  font-size: 12px;
  font-weight: 600;
  color: var(--danger);
  white-space: nowrap;
}
.sim-snippet {
  margin: 0;
  padding: 8px 10px;
  background: var(--bg-subtle);
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  white-space: pre-wrap;
  max-height: 120px;
  overflow-y: auto;
}
</style>
