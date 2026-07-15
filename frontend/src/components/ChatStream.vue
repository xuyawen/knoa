<script setup lang="ts">
import { useChatStore } from '@/stores/chat'
import { useKnowledgeStore } from '@/stores/knowledge'
import MessageBubble from './MessageBubble.vue'
import Icon from './Icon.vue'

const chat = useChatStore()
const knowledge = useKnowledgeStore()

const emit = defineEmits<{ (e: 'cite', id: number): void }>()

// 知识域药丸：点击切换 knowledge.activeBase，与左侧边栏选库同源，
// 真正影响 /api/ask 的检索范围（之前只是本地变量 activeFilter，不生效）
const filters: { label: string; key: string | null }[] = [
  { label: '全部', key: null },
  { label: '合规库', key: 'compliance' },
  { label: '广告投放', key: 'ads' },
  { label: '物流仓储', key: 'logistics' },
]
</script>

<template>
  <div class="chat-col">
    <!-- 知识域筛选药丸 -->
    <div class="filter-bar">
      <button
        v-for="f in filters"
        :key="f.label"
        class="pill"
        :class="{ active: f.key === knowledge.activeBase }"
        @click="knowledge.selectBase(f.key)"
      >
        {{ f.label }}
      </button>
    </div>

    <!-- 对话流 -->
    <div class="chat-scroll">
      <MessageBubble
        v-for="m in chat.messages"
        :key="m.id"
        :message="m"
        @cite="emit('cite', $event)"
      />
      <div v-if="chat.sources.length" class="hint">
        <Icon name="sparkle" :size="14" />
        <span>答案由知海基于知识库检索生成，点击角标可查看溯源</span>
      </div>
    </div>
  </div>
</template>


<style scoped>
.chat-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  background: var(--bg-page);
}
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 24px;
  flex-shrink: 0;
}
.pill {
  height: 34px;
  padding: 0 16px;
  border-radius: var(--radius-pill);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  transition: all 0.15s ease;
}
.pill:first-child {
  padding: 0 20px;
}
.pill:hover {
  border-color: var(--brand);
  color: var(--brand);
}
.pill.active {
  background: var(--brand-soft);
  color: var(--brand);
  border-color: transparent;
}
.chat-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.hint {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-placeholder);
  font-size: 12px;
  padding: 4px 2px;
}
.hint :deep(svg) {
  color: var(--brand);
}
</style>
