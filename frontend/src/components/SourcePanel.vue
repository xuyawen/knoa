<script setup lang="ts">
import { computed, ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useKnowledgeStore } from '@/stores/knowledge'
import SourceCard from './SourceCard.vue'
import SourceDetailDrawer from './SourceDetailDrawer.vue'
import Icon from './Icon.vue'
import HealthBar from './HealthBar.vue'
import TrendingList from './TrendingList.vue'

const chat = useChatStore()
const knowledge = useKnowledgeStore()

// 三个模块默认折叠，点击标题展开看详情
const srcOpen = ref(false)
const healthOpen = ref(false)
const trendOpen = ref(false)

const avgHealth = computed(() => {
  const list = knowledge.health
  if (!list.length) return 0
  const sum = list.reduce((a, h) => a + (h.health_score || 0), 0)
  return Math.round((sum / list.length) * 100)
})

const emit = defineEmits<{
  (e: 'locate', id: number): void
  (e: 'ask', q: string): void
}>()
</script>

<template>
  <div class="panel">
    <!-- 答案溯源 -->
    <div class="section">
      <button class="section-head" @click="srcOpen = !srcOpen">
        <span class="section-title">答案溯源</span>
        <span class="section-summary">
          {{ chat.sources.length ? chat.sources.length + ' 个来源' : '暂无来源' }}
        </span>
        <Icon name="chevron-down" :size="14" class="section-caret" :class="{ closed: !srcOpen }" />
      </button>
      <div v-show="srcOpen" class="section-body">
        <div v-if="chat.sources.length === 0" class="empty">
          提问后这里会显示答案来源
        </div>
        <SourceCard
          v-for="s in chat.sources"
          :key="s.id"
          :source="s"
          :active="chat.activeSourceId === s.id"
          @locate="emit('locate', $event)"
          @open="chat.openSource($event)"
        />
      </div>
    </div>

    <div class="divider" />

    <!-- 知识库健康度 -->
    <div class="section">
      <button class="section-head" @click="healthOpen = !healthOpen">
        <span class="section-title">知识库健康度</span>
        <span class="section-summary">
          {{ knowledge.health.length }} 个知识库 · 平均 {{ avgHealth }}%
        </span>
        <Icon name="chevron-down" :size="14" class="section-caret" :class="{ closed: !healthOpen }" />
      </button>
      <div v-show="healthOpen" class="section-body">
        <div class="health-list">
          <HealthBar
            v-for="h in knowledge.health"
            :key="h.kb"
            :item="h"
          />
        </div>
      </div>
    </div>

    <div class="divider" />

    <!-- 今日高频 -->
    <div class="section">
      <button class="section-head" @click="trendOpen = !trendOpen">
        <span class="section-title">今日高频</span>
        <span class="section-summary">
          {{ knowledge.trending.length }} 个热门问题
        </span>
        <Icon name="chevron-down" :size="14" class="section-caret" :class="{ closed: !trendOpen }" />
      </button>
      <div v-show="trendOpen" class="section-body">
        <TrendingList @ask="emit('ask', $event)" />
      </div>
    </div>

    <SourceDetailDrawer
      :detail="chat.activeSourceDetail"
      :loading="chat.loadingSource"
      @close="chat.closeSourceDetail()"
    />
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
.section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 0;
  margin: 0 0 12px;
  background: none;
  border: none;
  cursor: pointer;
  font: inherit;
  color: inherit;
  text-align: left;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}
.section-summary {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-placeholder);
}
.section-caret {
  margin-left: auto;
  color: var(--text-placeholder);
  transition: transform 0.2s ease;
}
.section-caret.closed {
  transform: rotate(-90deg);
}
.section-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.health-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.empty {
  font-size: 12px;
  color: var(--text-placeholder);
  padding: 12px 0;
}
.divider {
  height: 1px;
  flex-shrink: 0;
  background: var(--border);
  margin: 4px 0;
}
</style>
