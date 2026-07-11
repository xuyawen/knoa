<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import MessageBubble from './MessageBubble.vue'
import Icon from './Icon.vue'

const chat = useChatStore()

const emit = defineEmits<{ (e: 'cite', id: number): void }>()

const filters = ['全部', '合规库', '广告投放', '物流仓储']
const activeFilter = ref('全部')
</script>

<template>
  <div class="chat-col">
    <!-- 知识域筛选药丸 -->
    <div class="filter-bar">
      <button
        v-for="f in filters"
        :key="f"
        class="pill"
        :class="{ active: f === activeFilter }"
        @click="activeFilter = f"
      >
        {{ f }}
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
      <div v-if="chat.streaming && chat.messages.length > 0 && chat.messages[chat.messages.length - 1].content === ''" class="typing">
        <span class="dot" /><span class="dot" /><span class="dot" />
      </div>
      <div class="hint">
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
.typing {
  display: flex;
  gap: 4px;
  padding: 8px 2px;
}
.typing .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-placeholder);
  animation: bounce 1.2s infinite;
}
.typing .dot:nth-child(2) { animation-delay: 0.2s; }
.typing .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
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
