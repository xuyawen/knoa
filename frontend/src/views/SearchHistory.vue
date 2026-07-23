<script setup lang="ts">
// 搜索历史页：展示本地搜索历史，可点击重搜、单条删除、一键清空。
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Icon from '@/components/ui/Icon.vue'
import { useSearchHistory } from '@/composables/useSearchHistory'

const router = useRouter()
const { history, load, clear, remove } = useSearchHistory()

onMounted(load)

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
    <div class="page-header">
      <h2 class="page-title">
        <Icon name="clock" :size="18" /> 搜索历史
      </h2>
      <button v-if="history.length" class="btn-link muted" @click="clear">清空全部</button>
    </div>

    <div class="card list-page">
      <div v-if="history.length" class="history-list">
        <div
          v-for="h in history"
          :key="h"
          class="history-row"
          @click="reSearch(h)"
        >
          <Icon name="clock" :size="14" class="row-icon" />
          <span class="row-text">{{ h }}</span>
          <button class="row-action" title="删除" @click.stop="removeItem(h, $event)">
            <Icon name="trash-2" :size="14" />
          </button>
        </div>
      </div>
      <div v-else class="empty-page">
        <Icon name="clock" :size="40" />
        <div>暂无搜索历史</div>
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

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 2px;
}
.page-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.list-page {
  flex: 1;
  padding: 8px 0;
  min-height: 300px;
}
.history-list {
  display: flex;
  flex-direction: column;
}
.history-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
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
  gap: 12px;
  min-height: 260px;
  color: var(--text-tertiary);
  font-size: 13px;
}
</style>
