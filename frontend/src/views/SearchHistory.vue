<script setup lang="ts">
// 搜索历史页：统计 + 热门搜索 + 按日期分组的历史记录。
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Icon from '@/components/ui/Icon.vue'
import { useSearchHistory } from '@/composables/useSearchHistory'
import { useTrending } from '@/composables/useTrending'

const router = useRouter()
const { history, load, clear, remove, todayCount, weekCount, groupByDate } = useSearchHistory()
const { trending, load: loadTrending } = useTrending()

onMounted(() => {
  load()
  loadTrending()
})

// 热门搜索取前 8 条，排除已在历史中的（避免重复）
const hotSuggestions = computed(() => {
  const historyTexts = new Set(history.value.map((h) => h.text))
  return trending.value.filter((t) => !historyTexts.has(t.question)).slice(0, 8)
})

function reSearch(text: string) {
  router.push({ path: '/search', query: { q: text } })
}
function removeItem(text: string, e: Event) {
  e.stopPropagation()
  remove(text)
}
</script>

<template>
  <div class="search-page">
    <!-- 统计条 -->
    <div class="stats-row">
      <div class="stat-item">
        <span class="stat-num">{{ history.length }}</span>
        <span class="stat-label">历史记录</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-num">{{ todayCount() }}</span>
        <span class="stat-label">今日搜索</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-num">{{ weekCount() }}</span>
        <span class="stat-label">近7天</span>
      </div>
      <div v-if="history.length" class="stat-actions">
        <button class="btn btn-primary btn-sm" @click="clear">清空全部</button>
      </div>
    </div>

    <!-- 主内容：历史 + 热门 -->
    <div class="main-grid">
      <!-- 左：按日期分组的历史 -->
      <div class="card history-panel">
        <template v-if="history.length">
          <div v-for="group in groupByDate()" :key="group.label" class="date-group">
            <div class="date-label">{{ group.label }}</div>
            <div
              v-for="h in group.items"
              :key="h.text"
              class="history-row"
              @click="reSearch(h.text)"
            >
              <Icon name="clock" :size="14" class="row-icon" />
              <span class="row-text">{{ h.text }}</span>
              <button class="row-action" title="删除" @click.stop="removeItem(h.text, $event)">
                <Icon name="trash-2" :size="14" />
              </button>
            </div>
          </div>
        </template>
        <div v-else class="empty-page">
          <Icon name="clock" :size="40" />
          <div>暂无搜索历史</div>
          <p>去智能搜索试试吧</p>
        </div>
      </div>

      <!-- 右：热门搜索推荐 -->
      <div class="card hot-panel">
        <div class="panel-head">
          <Icon name="fire" :size="15" />
          <span>热门搜索</span>
        </div>
        <template v-if="hotSuggestions.length">
          <div
            v-for="(t, i) in hotSuggestions"
            :key="t.question"
            class="hot-item"
            @click="reSearch(t.question)"
          >
            <span class="hot-rank" :class="'rk-' + Math.min(i + 1, 3)">{{ i + 1 }}</span>
            <span class="hot-q">{{ t.question }}</span>
            <span class="hot-count">{{ t.count }}次</span>
          </div>
        </template>
        <div v-else class="empty-hint">暂无热门数据</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.search-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  min-height: 0;
}

/* ── 统计条 ── */
.stats-row {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 16px 20px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}
.stat-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.stat-num {
  font-size: 22px;
  font-weight: 800;
  color: var(--brand);
  line-height: 1;
}
.stat-label {
  font-size: 12.5px;
  color: var(--text-secondary);
}
.stat-divider {
  width: 1px;
  height: 24px;
  background: var(--border);
}
.stat-actions {
  margin-left: auto;
}

/* ── 主内容双栏 ── */
.main-grid {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

/* ── 历史面板 ── */
.history-panel {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 4px 0;
  min-height: 0;
}
.date-group {
  display: flex;
  flex-direction: column;
}
.date-label {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 10px 18px 6px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.history-list,
.date-group {
  display: flex;
  flex-direction: column;
}
.history-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 18px;
  cursor: pointer;
  transition: background var(--dur-fast);
}
.history-row:hover { background: var(--bg-hover); }
.row-icon { color: var(--text-tertiary); flex-shrink: 0; }
.row-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13.5px;
  color: var(--text-primary);
}
.row-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px; height: 28px;
  border-radius: 6px;
  color: var(--text-tertiary);
  background: transparent;
  border: none;
  opacity: 0;
  transition: all var(--dur-fast);
}
.history-row:hover .row-action { opacity: 1; }
.row-action:hover { background: var(--danger-soft); color: var(--danger); }

.empty-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 260px;
  color: var(--text-tertiary);
  font-size: 13px;
}
.empty-page p { margin: 0; opacity: 0.7; }

/* ── 热门搜索侧栏 ── */
.hot-panel {
  padding: 14px 16px;
  max-height: 100%;
  overflow-y: auto;
}
.panel-head {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
}
.panel-head .icon-wrap { color: #f97316; }
.hot-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 8px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--dur-fast);
}
.hot-item:hover { background: var(--bg-hover); }
.hot-rank {
  width: 20px; height: 20px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%;
  font-size: 11.5px;
  font-weight: 800;
  flex-shrink: 0;
  background: var(--bg-subtle);
  color: var(--text-tertiary);
}
.hot-rank.rk-1 { background: #fef2f2; color: #dc2626; }
.hot-rank.rk-2 { background: #fff7ed; color: #ea580c; }
.hot-rank.rk-3 { background: #fffbeb; color: #d97706; }
.hot-q {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--text-primary);
}
.hot-count {
  font-size: 11.5px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.empty-hint {
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
  padding: 24px 0;
}

@media (max-width: 768px) {
  .main-grid { grid-template-columns: 1fr; }
  .stats-row { flex-wrap: wrap; gap: 12px; }
  .stat-actions { margin-left: 0; width: 100%; }
}
</style>
