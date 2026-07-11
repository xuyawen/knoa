<script setup lang="ts">
import { sources, health } from '@/mocks/data'
import SourceCard from './SourceCard.vue'
import HealthBar from './HealthBar.vue'
import TrendingList from './TrendingList.vue'

const emit = defineEmits<{ (e: 'locate', id: number): void; (e: 'ask', q: string): void }>()
</script>

<template>
  <aside class="panel">
    <!-- 标题卡 -->
    <div class="panel-head">
      <div class="ph-title">答案溯源</div>
      <div class="ph-sub">{{ sources.length }} 条来源 · 实时检索</div>
    </div>

    <!-- 来源卡片 -->
    <SourceCard
      v-for="s in sources"
      :key="s.id"
      :source="s"
      @locate="emit('locate', $event)"
    />

    <div class="divider" />

    <!-- 知识库健康度 -->
    <div class="sec-title">知识库健康度</div>
    <div class="health-grid">
      <HealthBar v-for="h in health.slice(0, 3)" :key="h.kb" :item="h" />
    </div>

    <div class="divider" />

    <!-- 今日高频 -->
    <div class="sec-title">今日高频</div>
    <TrendingList @ask="emit('ask', $event)" />
  </aside>
</template>

<style scoped>
.panel {
  width: var(--rightpanel-w);
  flex-shrink: 0;
  min-width: 0;
  border-left: 1px solid var(--border);
  background: var(--bg-surface);
  overflow-y: auto;
  padding: 20px;
}
.panel-head {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  margin-bottom: 12px;
}
.ph-title {
  font-size: 15px;
  font-weight: 600;
}
.ph-sub {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.divider {
  height: 1px;
  background: var(--border);
  margin: 18px 0;
}
.sec-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 12px;
}
.health-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
</style>
