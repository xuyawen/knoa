<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import ChatStream from '@/components/ChatStream.vue'
import Composer from '@/components/Composer.vue'
import Icon from '@/components/Icon.vue'
import SourcePanel from '@/components/SourcePanel.vue'
import MobileWorkbench from '@/views/MobileWorkbench.vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useChatStore } from '@/stores/chat'
import { useSidebarCollapsed } from '@/composables/useSidebarCollapsed'
import type { ChatAttachment } from '@/types/api'

const knowledge = useKnowledgeStore()
const chat = useChatStore()
const { collapsed } = useSidebarCollapsed()
const isMobile = ref(false)
let mq: MediaQueryList | undefined

function onCollapse() {
  collapsed.value = true
}

function onExpand() {
  collapsed.value = false
}

function syncMobile() {
  isMobile.value = window.matchMedia('(max-width: 900px)').matches
}

function onAsk(q: string) {
  if (q.trim()) chat.ask(q, chat.filterKb ?? knowledge.activeBase)
}

function onSend(payload: { text: string; files: ChatAttachment[] }) {
  chat.ask(payload.text, chat.filterKb ?? knowledge.activeBase, payload.files)
}

function onCite(id: number) {
  chat.locateSource(id)
}

function onLocate(id: number) {
  chat.locateSource(id)
}

onMounted(() => {
  syncMobile()
  mq = window.matchMedia('(max-width: 900px)')
  mq.addEventListener('change', syncMobile)
  knowledge.load()
})
onUnmounted(() => mq?.removeEventListener('change', syncMobile))
</script>

<template>
  <MobileWorkbench v-if="isMobile" />

  <div v-else class="workbench">
    <AppSidebar :collapsed="collapsed" @collapse="onCollapse" @expand="onExpand" />
    <div class="main">
      <TopBar :title="knowledge.activeBase ? knowledge.bases.find(b => b.id === knowledge.activeBase)?.name ?? '' : ''">
        <template #actions-extra>
          <button class="new-chat-btn" @click="chat.startNewChat()" title="新建对话">
            <Icon name="plus" :size="16" />
          </button>
        </template>
      </TopBar>
      <div class="body">
        <div class="chat-wrap">
          <ChatStream @cite="onCite" />
          <Composer @send="onSend" />
        </div>
        <SourcePanel @locate="onLocate" @ask="onAsk" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.workbench {
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
  display: flex;
  min-height: 0;
}
.chat-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
.new-chat-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.new-chat-btn:hover {
  background: var(--brand-soft);
  color: var(--brand);
  border-color: transparent;
}
</style>
