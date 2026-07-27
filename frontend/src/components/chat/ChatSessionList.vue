<script setup lang="ts">
// 智能问答 — 左栏会话列表（懒加载滚动 + 删除/重命名入口），从 Chat.vue 拆出。
import { ref, nextTick } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import type { ChatSession } from '@/types/api'

const props = defineProps<{
  sessions: ChatSession[]
  total: number
  activeId: string | null
  loadingMore: boolean
  allLoaded: boolean
}>()

const emit = defineEmits<{
  (e: 'select', id: string): void
  (e: 'remove', id: string): void
  (e: 'rename', id: string, title: string): void
  (e: 'load-more'): void
}>()

/** 滚动到底部附近时通知父组件加载下一页 */
function onScroll(e: Event) {
  const el = e.target as HTMLElement
  if (!el || props.loadingMore || props.allLoaded) return
  const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
  if (nearBottom) emit('load-more')
}

// ---------- 内联重命名 ----------
const editingId = ref<string | null>(null)
const editText = ref('')

async function startRename(s: ChatSession) {
  editingId.value = s.id
  editText.value = s.title || ''
  await nextTick()
  const el = document.querySelector('.conv-rename-input') as HTMLInputElement | null
  el?.focus()
  el?.select()
}

/** 提交重命名（Enter / 失焦）；空标题视为放弃 */
function commitRename(id: string) {
  if (editingId.value !== id) return
  editingId.value = null
  const t = editText.value.trim()
  if (t) emit('rename', id, t)
}
</script>

<template>
  <aside class="chat-sidebar">
    <div class="sidebar-head">
      <div class="sidebar-title">
        <span>对话</span>
        <span class="sidebar-count">{{ total }}</span>
      </div>
    </div>

    <div class="conv-list" @scroll="onScroll">
      <!-- 用 div(role=button) 而非 button：重命名输入框不能嵌套在 button 里（HTML 不允许交互元素套交互元素） -->
      <div
        v-for="s in sessions"
        :key="s.id"
        class="conv-item"
        role="button"
        :class="{ active: s.id === activeId }"
        @click="emit('select', s.id)"
      >
        <span class="conv-dot" />
        <span class="conv-body">
          <input
            v-if="editingId === s.id"
            v-model="editText"
            class="conv-rename-input"
            maxlength="60"
            @click.stop
            @keydown.enter="commitRename(s.id)"
            @keydown.esc="editingId = null"
            @blur="commitRename(s.id)"
          />
          <span v-else class="conv-q">{{ s.title || '（新会话）' }}</span>
          <span class="conv-meta">
            <span class="conv-time">{{ s.updatedAt ? s.updatedAt.slice(5, 10) : '' }}</span>
            <span class="conv-sep">·</span>
            <span>{{ s.msgCount }} 条</span>
          </span>
        </span>
        <span class="conv-edit" title="重命名会话" @click.stop="startRename(s)">
          <Icon name="edit" :size="13" />
        </span>
        <span class="conv-del" title="删除会话" @click.stop="emit('remove', s.id)">
          <Icon name="trash" :size="14" />
        </span>
      </div>
      <p v-if="!sessions.length && !loadingMore" class="conv-empty">还没有对话，点击右上角开始。</p>
      <div v-if="loadingMore" class="conv-loading-more">
        <span class="dot-sm" /><span class="dot-sm" /><span class="dot-sm" />
      </div>
      <p v-if="allLoaded && sessions.length > 0" class="conv-all-done">已全部加载</p>
    </div>
  </aside>
</template>

<style scoped>
.chat-sidebar {
  width: 272px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg-surface);
}
.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 18px 14px;
}
.sidebar-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}
.sidebar-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
  background: var(--bg-subtle);
  padding: 1px 8px;
  border-radius: var(--radius-pill);
}
.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.conv-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 11px 12px;
  border-radius: var(--radius-md);
  text-align: left;
  color: var(--text-secondary);
  transition: background var(--dur-fast) var(--ease-out);
}
.conv-item:hover { background: var(--bg-hover); }
.conv-item.active {
  background: var(--brand-soft);
  color: var(--text-primary);
}
.conv-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-tertiary);
  flex-shrink: 0;
  transition: background var(--dur-fast);
}
.conv-item.active .conv-dot { background: var(--brand); }
.conv-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.conv-q {
  font-size: 13px;
  font-weight: 600;
  color: inherit;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-item.active .conv-q { color: var(--brand); }
.conv-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-tertiary);
}
.conv-sep { opacity: 0.6; }
.conv-del {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  opacity: 0;
  transition: all var(--dur-fast) var(--ease-out);
}
.conv-item:hover .conv-del { opacity: 1; }
.conv-item:hover .conv-edit { opacity: 1; }
.conv-del:hover { background: var(--danger-soft); color: var(--danger); }
.conv-edit {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  opacity: 0;
  transition: all var(--dur-fast) var(--ease-out);
}
.conv-edit:hover { background: var(--brand-soft); color: var(--brand); }
.conv-rename-input {
  width: 100%;
  padding: 3px 8px;
  border: 1px solid var(--brand);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 12.5px;
  font-weight: 600;
  outline: none;
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.conv-empty {
  margin: 24px 8px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-tertiary);
  text-align: center;
}
.conv-loading-more {
  display: flex;
  justify-content: center;
  gap: 4px;
  padding: 12px 0 6px;
}
.dot-sm {
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--text-tertiary);
  animation: blink 1.3s infinite ease-in-out;
}
.conv-loading-more .dot-sm:nth-child(2) { animation-delay: 0.18s; }
.conv-loading-more .dot-sm:nth-child(3) { animation-delay: 0.36s; }
.conv-all-done {
  text-align: center;
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
}
@keyframes blink { 0%, 80%, 100% { opacity: 0.25; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-3px); } }

@media (max-width: 720px) {
  .chat-sidebar { width: 210px; }
}
</style>
