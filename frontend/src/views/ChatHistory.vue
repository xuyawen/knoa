<script setup lang="ts">
import { onMounted } from 'vue'
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
  if (route.path !== '/') router.push('/')
}

async function onNew() {
  await chat.startNewChat()
  if (route.path !== '/') router.push('/')
}

onMounted(() => chat.loadSessions())
</script>

<template>
  <div class="history-page">
    <AppSidebar :collapsed="collapsed" @collapse="onCollapse" @expand="onExpand" />
    <div class="main">
      <TopBar title="问答记录">
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
  .body {
    padding: 16px;
  }
}
</style>
