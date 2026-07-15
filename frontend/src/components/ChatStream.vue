<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useKnowledgeStore } from '@/stores/knowledge'
import MessageBubble from './MessageBubble.vue'
import Icon from './Icon.vue'

const chat = useChatStore()
const knowledge = useKnowledgeStore()

const emit = defineEmits(['cite'])

// 知识域下拉选择器（替代之前的一排药丸，解决 KB 多时两行挤的问题）
const dropdownOpen = ref(false)
const triggerRef = ref<HTMLElement | null>(null)

const options = computed(() => [
  { label: '全部知识库', key: null as string | null },
  ...knowledge.bases.map((b) => ({ label: b.name, key: b.id })),
])

const currentLabel = computed(() => {
  const found = options.value.find((o) => o.key === chat.filterKb)
  return found?.label || '全部知识库'
})

function toggleDropdown() {
  dropdownOpen.value = !dropdownOpen.value
}

function selectOption(key: string | null) {
  chat.filterKb = key
  dropdownOpen.value = false
}

// 点击外部关闭
function onClickOutside(e: MouseEvent) {
  if (triggerRef.value && !triggerRef.value.contains(e.target as Node)) {
    dropdownOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside))
</script>

<template>
  <div class="chat-col">
    <!-- 知识域下拉选择器 -->
    <div class="filter-bar" ref="triggerRef">
      <button class="dropdown-trigger" @click.stop="toggleDropdown">
        <span class="trigger-label">{{ currentLabel }}</span>
        <Icon name="chevron-down" :size="14" :class="{ rotated: dropdownOpen }" />
      </button>
      <transition name="dropdown">
        <div v-if="dropdownOpen" class="dropdown-menu">
          <button
            v-for="o in options"
            :key="o.key ?? '__all__'"
            class="dropdown-item"
            :class="{ active: o.key === chat.filterKb }"
            @click="selectOption(o.key)"
          >
            {{ o.label }}
          </button>
        </div>
      </transition>
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
  position: relative;
  display: flex;
  align-items: center;
  padding: 12px 24px;
  flex-shrink: 0;
}
.dropdown-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}
.dropdown-trigger:hover {
  border-color: var(--brand);
  color: var(--brand);
}
.trigger-label {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dropdown-trigger svg.rotated {
  transform: rotate(180deg);
}
.dropdown-menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 24px;
  min-width: 180px;
  max-height: 280px;
  overflow-y: auto;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 50;
  padding: 4px;
}
.dropdown-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.12s ease;
  white-space: nowrap;
}
.dropdown-item:hover {
  background: var(--bg-hover);
}
.dropdown-item.active {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
}

/* 下拉动画 */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.15s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
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
