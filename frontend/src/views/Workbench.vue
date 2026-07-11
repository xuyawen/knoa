<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import ChatStream from '@/components/ChatStream.vue'
import Composer from '@/components/Composer.vue'
import SourcePanel from '@/components/SourcePanel.vue'
import MobileWorkbench from '@/views/MobileWorkbench.vue'
import { knowledgeBases } from '@/mocks/data'

const activeBase = ref('compliance')
const title = ref('全部知识')
const collapsed = ref(false)
const isMobile = ref(false)

let mq: MediaQueryList | undefined

function syncMobile() {
  isMobile.value = window.matchMedia('(max-width: 900px)').matches
}

function onSelectBase(id: string) {
  activeBase.value = id
  const kb = knowledgeBases.find((k) => k.id === id)
  if (kb) title.value = kb.name
}
function onAsk(q: string) {
  console.log('ask:', q)
}
function onSend(q: string) {
  console.log('send:', q)
}
function onCite(id: number) {
  console.log('cite:', id)
}
function onLocate(id: number) {
  console.log('locate:', id)
}

onMounted(() => {
  syncMobile()
  mq = window.matchMedia('(max-width: 900px)')
  mq.addEventListener('change', syncMobile)
})
onUnmounted(() => mq?.removeEventListener('change', syncMobile))
</script>

<template>
  <MobileWorkbench v-if="isMobile" />

  <div v-else class="workbench">
    <AppSidebar
      :active-base="activeBase"
      :collapsed="collapsed"
      @select-base="onSelectBase"
      @collapse="collapsed = !collapsed"
    />
    <div class="main">
      <TopBar :title="title" @ask="onAsk" />
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
