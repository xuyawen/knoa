<script setup lang="ts">
import { useChatStore } from '@/stores/chat'
import { useKnowledgeStore } from '@/stores/knowledge'
import SourceCard from './SourceCard.vue'
import HealthBar from './HealthBar.vue'
import TrendingList from './TrendingList.vue'

const chat = useChatStore()
const knowledge = useKnowledgeStore()

const emit = defineEmits<{
  (e: 'locate', id: number): void
  (e: 'ask', q: string): void
}>()
</script>

<template>
  <div class="panel">
    <!-- 答案溯源 -->
    <div class="section">
      <div class="section-title">答案溯源</div>
      <div v-if="chat.sources.length === 0" class="empty">
        提问后这里会显示答案来源
      </div>
      <SourceCard
        v-for="s in chat.sources"
        :key="s.id"
        :source="s"
        :active="chat.activeSourceId === s.id"
        @locate="emit('locate', $event)"
      />
    </div>

    <div class="divider" />

    <!-- 知识库健康度 -->
    <div class="section">
      <div class="section-title">知识库健康度</div>
      <HealthBar
        v-for="h in knowledge.health"
        :key="h.kb"
        :item="h"
      />
    </div>

    <div class="divider" />

    <!-- 今日高频 -->
    <div class="section">
      <div class="section-title">今日高频</div>
      <TrendingList @ask="emit('ask', $event)" />
    </div>
  </div>
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
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 12px;
}
.empty {
  font-size: 12px;
  color: var(--text-placeholder);
  padding: 12px 0;
}
.divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}
</style>
