<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import Icon from '@/components/Icon.vue'
import { useChatStore } from '@/stores/chat'
import { useSidebarCollapsed } from '@/composables/useSidebarCollapsed'
import { useConfirm } from '@/composables/useConfirm'

const { confirm } = useConfirm()

const router = useRouter()
const route = useRoute()
const chat = useChatStore()
const { collapsed } = useSidebarCollapsed()

const isMobile = ref(false)
const drawer = ref(false)
let mq: MediaQueryList | undefined

// ── 多选 / 删除（勾选即选，无需进入模式）──
const selectedIds = ref<Set<string>>(new Set())
const hoverId = ref<string | null>(null)

function onCheck(id: string, e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  const next = new Set(selectedIds.value)
  if (checked) next.add(id)
  else next.delete(id)
  selectedIds.value = next
}

async function handleDeleteOne(id: string) {
  const ok = await confirm({
    title: '删除会话',
    message: '确定删除此会话？会话内的全部消息将一并清除，且无法恢复。',
    confirmText: '删除',
    danger: true,
    onConfirm: async () => { await chat.removeSession(id) },
  })
  if (ok) {
    const next = new Set(selectedIds.value)
    next.delete(id)
    selectedIds.value = next
  }
}

async function handleBatchDelete() {
  const ids = Array.from(selectedIds.value)
  if (ids.length === 0) return
  const ok = await confirm({
    title: '批量删除',
    message: `确定删除选中的 ${ids.length} 个会话？会话内的全部消息将一并清除，且无法恢复。`,
    confirmText: `删除 ${ids.length} 个`,
    danger: true,
    onConfirm: async () => { await chat.removeSessions(ids) },
  })
  if (ok) selectedIds.value = new Set()
}

function syncMobile() {
  isMobile.value = window.matchMedia('(max-width: 900px)').matches
}

function onCollapse() {
  collapsed.value = true
}

function onExpand() {
  collapsed.value = false
}

function fmtTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前'
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

async function onPick(id: string) {
  await chat.switchSession(id)
  if (isMobile.value) {
    router.push('/')
  } else if (route.path !== '/') {
    router.push('/')
  }
}

async function onNew() {
  await chat.startNewChat()
  if (isMobile.value) {
    router.push('/')
  } else if (route.path !== '/') {
    router.push('/')
  }
}

onMounted(() => {
  syncMobile()
  mq = window.matchMedia('(max-width: 900px)')
  mq.addEventListener('change', syncMobile)
  chat.loadSessions()
})
onUnmounted(() => mq?.removeEventListener('change', syncMobile))
</script>

<template>
  <div class="history-page">
    <AppSidebar :collapsed="collapsed" :mobile-open="drawer" @collapse="onCollapse" @expand="onExpand" @close="drawer = false" />
    <div v-if="isMobile && drawer" class="overlay" @click="drawer = false" />

    <!-- 移动端顶栏 -->
    <header v-if="isMobile" class="m-top">
      <button class="m-menu" @click="drawer = true" title="菜单">
        <Icon name="menu" :size="20" />
      </button>
      <span class="m-title">问答记录</span>
      <div class="m-top-right">
        <button class="m-new-btn" @click="onNew" title="新建对话">
          <Icon name="plus" :size="16" />
        </button>
        <button v-if="selectedIds.size > 0" class="m-act-btn" @click="handleBatchDelete" title="删除选中">
          <Icon name="trash" :size="16" />
        </button>
        <button class="m-back" @click="router.push('/')">返回</button>
      </div>
    </header>

    <div class="main">
      <!-- 桌面端顶栏 -->
      <div v-if="!isMobile" class="toolbar-row">
        <TopBar title="问答记录" />
      </div>

      <div class="body">
        <!-- 列表操作区：新建 + 批量删除 -->
        <div v-if="!isMobile" class="list-toolbar">
          <div class="list-toolbar-left">
            <button class="new-btn" @click="onNew">
              <Icon name="plus" :size="15" /> 新建对话
            </button>
            <button
              v-if="selectedIds.size > 0"
              class="sel-btn"
              @click="handleBatchDelete"
              title="批量删除"
            >
              <Icon name="check-square" :size="15" /> 批量删除（{{ selectedIds.size }}）
            </button>
          </div>
        </div>

        <div v-if="chat.loadingHistory" class="empty">加载中…</div>
        <div v-else-if="chat.sessions.length === 0" class="empty">还没有对话记录</div>
        <div v-else class="session-list">
          <div
            v-for="s in chat.sessions"
            :key="s.id"
            class="session-item"
            :class="{ active: s.id === chat.sessionId, checked: selectedIds.has(s.id) }"
          >
            <!-- 勾选框始终显示，勾选即选 -->
            <label class="check-wrap" @click.stop>
              <input
                type="checkbox"
                class="app-checkbox"
                :checked="selectedIds.has(s.id)"
                @change="onCheck(s.id, $event)"
              />
            </label>

            <button class="session-body" @click="onPick(s.id)">
              <div class="session-title">{{ s.title }}</div>
              <div v-if="s.summary" class="session-summary">{{ s.summary }}</div>
              <div class="session-meta">
                <span>{{ s.msgCount }} 条消息</span>
                <span>{{ fmtTime(s.updatedAt) }}</span>
              </div>
            </button>

            <!-- 单个删除按钮（hover 显示） -->
            <button
              class="item-del"
              :class="{ show: s.id === hoverId }"
              @click.stop="handleDeleteOne(s.id)"
              @mouseenter="hoverId = s.id"
              @mouseleave="hoverId = null"
              title="删除此会话"
            >
              <Icon name="trash" :size="13" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-page {
  display: flex;
  height: 100%;
  overflow-x: hidden;
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.body {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
}

.toolbar-row {
  flex-shrink: 0;
}

.new-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: var(--btn-padding-md);
  height: var(--btn-height);
  background: var(--brand);
  color: #fff;
  border-radius: var(--radius-md);
  font-size: var(--btn-font-size);
  font-weight: var(--btn-font-weight);
  transition: background 0.15s ease, transform 0.15s ease;
}
.new-btn:hover {
  background: var(--brand-hover);
}

.sel-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: var(--btn-padding-md);
  height: var(--btn-height);
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: var(--btn-font-size);
  font-weight: var(--btn-font-weight);
  cursor: pointer;
  transition: all 0.15s ease;
}
.sel-btn:hover {
  color: var(--brand);
  border-color: var(--brand);
}

/* ── 列表上方工具栏（新建对话 / 批量删除） ── */
.list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 4px;
  margin-bottom: 4px;
}
.list-toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── 会话列表项 ── */
.session-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  text-align: left;
  padding: 11px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  width: 100%;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}
.session-item:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-card);
  transform: translateY(-1px);
}
.session-item.active {
  border-color: var(--brand);
  background: var(--brand-soft);
}
.session-item.checked {
  border-color: var(--brand);
  background: rgba(99, 102, 241, 0.06);
}

/* 复选框 */
.check-wrap {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

/* 主体区域 */
.session-body {
  flex: 1;
  display: block;
  text-align: left;
  background: none;
  border: none;
  padding: 0;
  min-width: 0;
  cursor: pointer;
  color: inherit;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}
.session-summary {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 6px;
}
.session-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-placeholder);
}

/* 单条删除按钮 — 默认红色，低调显示；hover 加深 */
.item-del {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: #dc2626;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0.45;
  transition: opacity 0.15s ease, background 0.15s ease;
}
.item-del:hover,
.item-del.show {
  opacity: 1;
}
.item-del:hover {
  background: rgba(220, 38, 38, 0.08);
}

.empty {
  padding: 60px 16px;
  text-align: center;
  color: var(--text-placeholder);
  font-size: 14px;
}

@media (max-width: 900px) {
  .main {
    padding-top: var(--mobile-topbar-h);
  }
  .body {
    padding: 16px;
  }
}

/* 移动端顶栏 */
.m-top {
  position: fixed; top: 0; left: 0; right: 0;
  height: var(--mobile-topbar-h);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  z-index: 30;
}
.m-menu {
  width: 36px; height: 36px;
  border-radius: var(--radius-pill);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-primary);
}
.m-title {
  font-family: var(--font-display); font-size: 16px; font-weight: 600;
}
.m-back {
  font-size: 13px; color: var(--brand); font-weight: 500;
  background: none; border: none;
  cursor: pointer;
}
.m-top-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}
.m-new-btn {
  width: 32px; height: 32px;
  border-radius: var(--radius-pill);
  display: flex; align-items: center; justify-content: center;
  color: var(--brand);
  background: none; border: none;
  cursor: pointer;
}
.m-act-btn {
  width: 32px; height: 32px;
  border-radius: var(--radius-pill);
  display: flex; align-items: center; justify-content: center;
  color: #dc2626;
  background: none; border: none;
  cursor: pointer;
}
.m-cancel {
  font-size: 13px; color: var(--text-secondary);
  background: none; border: none;
  cursor: pointer;
}
.overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 35;
}
</style>
