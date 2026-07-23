<script setup lang="ts">
// 热门搜索页：展示热门搜索榜，点击条目跳转搜索。
import { useRouter } from 'vue-router'
import Icon from '@/components/ui/Icon.vue'
import { useTrending } from '@/composables/useTrending'

const router = useRouter()
const { trending } = useTrending()

function reSearch(text: string) {
  router.push({ path: '/search', query: { q: text } })
}
</script>

<template>
  <div class="search-page">
    <div class="page-header">
      <h2 class="page-title">
        <Icon name="fire" :size="18" /> 热门搜索
      </h2>
    </div>

    <div class="card list-page">
      <div v-if="trending.length" class="trending-list">
        <div
          v-for="(t, i) in trending.slice(0, 10)"
          :key="t.question"
          class="trending-row"
          @click="reSearch(t.question)"
        >
          <span class="trend-rank" :class="'rk-' + Math.min(i + 1, 3)">{{ i + 1 }}</span>
          <span class="row-text">{{ t.question }}</span>
          <span class="trend-count" v-if="t.count">{{ t.count }} 次</span>
        </div>
      </div>
      <div v-else class="empty-page">
        <Icon name="fire" :size="40" />
        <div>暂无热门数据</div>
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
.trending-list {
  display: flex;
  flex-direction: column;
}
.trending-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  cursor: pointer;
  transition: background var(--dur-fast);
}
.trending-row:hover { background: var(--bg-hover); }
.row-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13.5px;
  color: var(--text-primary);
}
.trend-rank {
  width: 22px; height: 22px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 6px;
  font-size: 12px; font-weight: 700;
  background: var(--bg-subtle); color: var(--text-secondary);
  flex-shrink: 0;
}
.trend-rank.rk-1 { background: var(--brand); color: var(--text-on-brand); }
.trend-rank.rk-2 { background: var(--brand-soft); color: var(--brand); }
.trend-rank.rk-3 { background: var(--warning-soft); color: var(--warning); }
.trend-count {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

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
