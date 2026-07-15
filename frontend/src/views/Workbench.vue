<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import ChatStream from '@/components/ChatStream.vue'
import Composer from '@/components/Composer.vue'
import SourcePanel from '@/components/SourcePanel.vue'
import MobileWorkbench from '@/views/MobileWorkbench.vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useChatStore } from '@/stores/chat'
import { useSidebarCollapsed } from '@/composables/useSidebarCollapsed'

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
  if (q.trim()) chat.ask(q, knowledge.activeBase)
  else chat.focusComposer()
}

function onSend(q: string) {
  chat.ask(q, knowledge.activeBase)
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
      <TopBar :title="knowledge.activeBase ? knowledge.bases.find(b => b.id === knowledge.activeBase)?.name || '全部知识' : '全部知识'" @ask="onAsk" />
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
}
</style>
