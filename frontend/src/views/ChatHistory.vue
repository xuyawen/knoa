<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import Icon from '@/components/Icon.vue'
import { useChatStore } from '@/stores/chat'
import { useSidebarCollapsed } from '@/composables/useSidebarCollapsed'

const router = useRouter()
const route = useRoute()
const chat = useChatStore()
const { collapsed } = useSidebarCollapsed()

const isMobile = ref(false)
const drawer = ref(false)
let mq: MediaQueryList | undefined

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
        <button class="m-back" @click="router.push('/')">返回</button>
      </div>
    </header>

    <div class="main">
      <TopBar v-if="!isMobile" title="问答记录">
        <button class="new-btn" @click="onNew">
          <Icon name="plus" :size="15" /> 新建对话
        </button>
      </TopBar>
      <div class="body">
        <div v-if="chat.loadingHistory" class="empty">加载中…</div>
        <div v-else-if="chat.sessions.length === 0" class="empty">还没有对话记录</div>
        <div v-else class="session-list">
          <button
            v-for="s in chat.sessions"
            :key="s.id"
            class="session-item"
            :class="{ active: s.id === chat.sessionId }"
            @click="onPick(s.id)"
          >
            <div class="session-title">{{ s.title }}</div>
            <div v-if="s.summary" class="session-summary">{{ s.summary }}</div>
            <div class="session-meta">
              <span>{{ s.msgCount }} 条消息</span>
              <span>{{ fmtTime(s.updatedAt) }}</span>
            </div>
          </button>
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

.new-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 7px 14px;
  background: var(--brand);
  color: #fff;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  transition: background 0.15s ease;
}
.new-btn:hover {
  background: var(--brand-hover);
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.session-item {
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
  position: fixed;
  top: 0; left: 0; right: 0;
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
.overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 35;
}
.m-action {
  padding: calc(var(--mobile-topbar-h) + 8px) 16px 8px;
}
</style>
