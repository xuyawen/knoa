<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import Icon from './Icon.vue'

const chat = useChatStore()
const route = useRoute()
const router = useRouter()

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
</script>

<template>
  <Teleport to="body">
    <div v-if="chat.historyOpen" class="overlay" @click.self="chat.closeHistory()">
      <aside class="drawer">
        <header class="h-head">
          <h3 class="h-title">问答记录</h3>
          <div class="h-actions">
            <button class="h-new" @click="onNew">
              <Icon name="plus" :size="15" /> 新建对话
            </button>
            <button class="h-close" title="关闭" @click="chat.closeHistory()">×</button>
          </div>
        </header>
        <div class="h-body">
          <div v-if="chat.loadingHistory" class="h-empty">加载中…</div>
          <div v-else-if="chat.sessions.length === 0" class="h-empty">还没有对话记录</div>
          <button
            v-for="s in chat.sessions"
            :key="s.id"
            class="h-item"
            :class="{ active: s.id === chat.sessionId }"
            @click="onPick(s.id)"
          >
            <div class="h-item-title">{{ s.title }}</div>
            <div class="h-item-meta">
              <span>{{ s.msgCount }} 条消息</span>
              <span>{{ fmtTime(s.updatedAt) }}</span>
            </div>
          </button>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(2px);
  z-index: 60;
  display: flex;
  justify-content: flex-start;
  animation: fade 0.18s ease;
}
.drawer {
  width: min(340px, 88vw);
  height: 100%;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-float);
  animation: slide 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}
.h-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
}
.h-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  flex: 1;
}
.h-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.h-new {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: var(--brand);
  color: #fff;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 500;
  transition: background 0.15s ease;
}
.h-new:hover {
  background: var(--brand-hover);
}
.h-close {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 19px;
  line-height: 1;
  transition: background 0.15s ease;
}
.h-close:hover {
  background: var(--bg-subtle);
}
.h-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.h-item {
  text-align: left;
  padding: 12px 14px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: border-color 0.15s ease, background 0.15s ease;
}
.h-item:hover {
  border-color: var(--brand);
}
.h-item.active {
  border-color: var(--brand);
  background: var(--brand-soft);
}
.h-item-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}
.h-item-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-placeholder);
}
.h-empty {
  padding: 40px 16px;
  text-align: center;
  color: var(--text-placeholder);
  font-size: 13px;
}
@keyframes fade {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes slide {
  from { transform: translateX(-24px); opacity: 0.6; }
  to { transform: translateX(0); opacity: 1; }
}
</style>
