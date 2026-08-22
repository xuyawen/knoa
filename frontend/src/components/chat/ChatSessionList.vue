<script setup lang="ts">
// 智能问答 — 左栏会话列表（懒加载滚动 + 三点菜单：重命名/置顶/删除），从 Chat.vue 拆出。
// 交互参考主流对话产品：会话项默认纯净文本行，hover/选中时右侧浮现圆形三点按钮，
// 点击展开浮动菜单；删除项红色警示。
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
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
  (e: 'pin', id: string): void
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

// ---------- 三点浮动菜单 ----------
const menuFor = ref<string | null>(null)
const menuPos = ref({ top: 0, left: 0 })
const MENU_W = 148
const MENU_H = 138

/** 以三点按钮为锚点展开菜单；贴近视口底/左时翻转 */
function openMenu(s: ChatSession, e: MouseEvent) {
  if (menuFor.value === s.id) {
    menuFor.value = null
    return
  }
  const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
  let top = r.bottom + 6
  const left = Math.max(8, r.right - MENU_W)
  if (top + MENU_H > window.innerHeight - 8) top = r.top - MENU_H - 6
  menuPos.value = { top, left }
  menuFor.value = s.id
}

function onDocClick(e: MouseEvent) {
  if (!menuFor.value) return
  const t = e.target as HTMLElement
  if (t.closest('.conv-menu') || t.closest('.conv-more')) return
  menuFor.value = null
}
function onDocKey(e: KeyboardEvent) {
  if (e.key === 'Escape') menuFor.value = null
}
onMounted(() => {
  document.addEventListener('mousedown', onDocClick)
  window.addEventListener('keydown', onDocKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick)
  window.removeEventListener('keydown', onDocKey)
})

function actRename() {
  const s = props.sessions.find((x) => x.id === menuFor.value)
  menuFor.value = null
  if (s) void startRename(s)
}
function actPin() {
  const id = menuFor.value
  menuFor.value = null
  if (id) emit('pin', id)
}
function actRemove() {
  const id = menuFor.value
  menuFor.value = null
  if (id) emit('remove', id)
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
          <span v-else class="conv-q">
            <Icon v-if="s.pinned" name="pin" :size="11" class="conv-pin" />
            {{ s.title || '（新会话）' }}
          </span>
          <span class="conv-meta">
            <span class="conv-time">{{ s.updatedAt ? s.updatedAt.slice(5, 10) : '' }}</span>
            <span class="conv-sep">·</span>
            <span>{{ s.msgCount }} 条</span>
          </span>
        </span>
        <button
          class="conv-more"
          :class="{ show: menuFor === s.id }"
          title="更多操作"
          @click.stop="openMenu(s, $event)"
        >
          <Icon name="more" :size="15" />
        </button>
      </div>
      <p v-if="!sessions.length && !loadingMore" class="conv-empty">还没有对话，点击右上角开始。</p>
      <div v-if="loadingMore" class="conv-loading-more">
        <span class="dot-sm" /><span class="dot-sm" /><span class="dot-sm" />
      </div>
      <p v-if="allLoaded && total >= 20" class="conv-all-done">已全部加载</p>
    </div>

    <!-- 三点浮动菜单：Teleport 到 body 避免被侧栏 overflow 裁剪 -->
    <Teleport to="body">
      <div v-if="menuFor" class="conv-menu" :style="{ top: menuPos.top + 'px', left: menuPos.left + 'px' }">
        <button class="conv-menu-item" @click="actRename">
          <Icon name="edit" :size="14" />
          <span>重命名</span>
        </button>
        <button class="conv-menu-item" @click="actPin">
          <Icon :name="sessions.find((x) => x.id === menuFor)?.pinned ? 'pin-off' : 'pin'" :size="14" />
          <span>{{ sessions.find((x) => x.id === menuFor)?.pinned ? '取消置顶' : '置顶' }}</span>
        </button>
        <button class="conv-menu-item danger" @click="actRemove">
          <Icon name="trash" :size="14" />
          <span>删除</span>
        </button>
      </div>
    </Teleport>
  </aside>
</template>

<style scoped>
.chat-sidebar {
  width: 272px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  /* 独立圆角卡片，与右侧对话区并列（兄弟关系），不再嵌入对话区容器 */
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px 6px;
}
.sidebar-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
}
.sidebar-count {
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  color: var(--text-tertiary);
  background: var(--bg-subtle);
  padding: 0 6px;
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
  gap: 6px;
  width: 100%;
  padding: 10px 10px 10px 12px;
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
.conv-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.conv-q {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  font-weight: 600;
  color: inherit;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-pin { flex: none; color: var(--brand); }
.conv-item.active .conv-q { color: var(--brand); }
.conv-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-tertiary);
}
.conv-sep { opacity: 0.6; }
/* 三点按钮：默认隐藏，hover/选中/菜单展开时浮现（参考主流对话产品） */
.conv-more {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  color: var(--text-secondary);
  opacity: 0;
  transition: all var(--dur-fast) var(--ease-out);
}
.conv-item:hover .conv-more,
.conv-item.active .conv-more,
.conv-more.show { opacity: 1; }
.conv-more:hover { background: var(--border); color: var(--text-primary); }
/* 浮动菜单 */
.conv-menu {
  position: fixed;
  z-index: 300;
  width: 148px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-float);
}
.conv-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-primary);
  transition: background var(--dur-fast) var(--ease-out);
}
.conv-menu-item:hover { background: var(--bg-hover); }
.conv-menu-item.danger { color: var(--danger); }
.conv-menu-item.danger:hover { background: var(--danger-soft); }
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
  /* 窄屏：会话列表改覆盖式抽屉，不挤压对话区（定位上下文在 .chat-body） */
  .chat-sidebar {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    width: min(280px, 82%);
    z-index: 6;
    box-shadow: var(--shadow-float);
  }
}
</style>
