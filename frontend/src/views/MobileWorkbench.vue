<script setup lang="ts">
import { ref, computed } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useChatStore } from '@/stores/chat'
import AppSidebar from '@/components/AppSidebar.vue'
import Icon from '@/components/Icon.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import KnowledgeCard from '@/components/KnowledgeCard.vue'
import MobileNav from '@/components/MobileNav.vue'
import ChatStream from '@/components/ChatStream.vue'
import Composer from '@/components/Composer.vue'
import SourcePanel from '@/components/SourcePanel.vue'

const knowledge = useKnowledgeStore()
const chat = useChatStore()

const drawer = ref(false)
const tab = ref('home')
const question = ref('')
const showSources = ref(false)

const sourceCount = computed(() => chat.sources.length)

async function submit() {
  const q = question.value.trim()
  if (!q) return
  question.value = ''
  await knowledge.load()
  send(q)
}

function send(q: string) {
  chat.ask(q, knowledge.activeBase)
  tab.value = 'chat'
  showSources.value = false
}

function onCite(id: number) {
  chat.locateSource(id)
  if (sourceCount.value > 0) showSources.value = true
}

const kbCards = computed(() => {
  const healthMap = new Map(knowledge.health.map(h => [h.kb, h]))
  const fromKb = knowledge.bases.map(kb => {
    const h = healthMap.get(kb.name)
    return {
      icon: kb.icon,
      name: kb.name,
      alert: kb.badge?.includes('待复核'),
      meta: h ? `${h.docCount} 篇 · 健康 ${Math.round(h.healthScore * 100)}%` : '',
    }
  })
  const fromWs = ['文档管理'].map(e => ({
    icon: 'library',
    name: e,
    alert: false,
    meta: '快捷入口',
  }))
  return [...fromKb, ...fromWs]
})
</script>

<template>
  <div class="mwb">
    <!-- 抽屉侧栏 -->
    <AppSidebar :mobile-open="drawer" @close="drawer = false" />
    <div v-if="drawer" class="overlay" @click="drawer = false" />

    <!-- 顶栏 -->
    <header class="mtop">
      <button class="menu" @click="drawer = true" title="菜单">
        <Icon name="menu" :size="20" />
      </button>
      <span class="brand">知海 Knoa</span>
      <div class="actions">
        <ThemeToggle />
        <div class="account">运</div>
      </div>
    </header>

    <!-- 内容区：tab 切换带过渡（kb ↔ chat 等） -->
    <Transition name="tab" mode="out-in">
      <div
        class="pane"
        :class="{
          scroll: tab === 'home' || tab === 'kb' || tab === 'me',
          'scroll center': tab === 'me',
          'chat-view': tab === 'chat',
        }"
        :key="tab"
      >
        <!-- 首页 -->
        <template v-if="tab === 'home'">
          <div class="greet">
            <h2>你好，运营小王</h2>
            <p>向知海提问，获取带溯源的运营答案</p>
          </div>

          <form class="qcard" @submit.prevent="submit">
            <input
              v-model="question"
              type="text"
              placeholder="向知海提问…"
            />
            <button class="qsend" type="submit" title="发送">
              <Icon name="send" :size="16" />
            </button>
          </form>

          <div class="sec-title">知识库</div>
          <div class="kb-grid">
            <KnowledgeCard
              v-for="c in kbCards"
              :key="c.name"
              :icon="c.icon"
              :name="c.name"
              :meta="c.meta"
              :alert="c.alert"
            />
          </div>

          <div class="sec-title">今日高频</div>
          <ul class="trend">
            <li v-for="(t, i) in knowledge.trending" :key="i">
              <span class="rk" :class="{ top: i < 3 }">{{ i + 1 }}</span>
              <span class="tq">{{ t.question }}</span>
              <span class="tf"><Icon name="fire" :size="13" />{{ t.count }}</span>
            </li>
          </ul>
        </template>

        <!-- 知识库 -->
        <template v-else-if="tab === 'kb'">
          <div class="sec-title">知识库</div>
          <div class="kb-grid">
            <KnowledgeCard
              v-for="c in kbCards"
              :key="c.name"
              :icon="c.icon"
              :name="c.name"
              :meta="c.meta"
              :alert="c.alert"
            />
          </div>
        </template>

        <!-- 问答 -->
        <template v-else-if="tab === 'chat'">
          <div class="chat-bar">
            <span class="chat-title">知海问答</span>
            <button
              class="src-btn"
              :class="{ on: sourceCount > 0 }"
              :disabled="sourceCount === 0"
              @click="showSources = true"
            >
              <Icon name="search" :size="14" />
              溯源 {{ sourceCount }}
            </button>
          </div>

          <ChatStream class="chat-flex" @cite="onCite" />

          <Composer class="m-composer" @send="send" />
        </template>

        <!-- 我的 -->
        <template v-else>
          <div class="empty-me">
            <Icon name="user" :size="28" />
            <p>「我的」功能即将上线</p>
          </div>
        </template>
      </div>
    </Transition>

    <!-- 溯源底部弹层 -->
    <div v-if="showSources" class="sheet-mask" @click="showSources = false">
      <div class="sheet" @click.stop>
        <div class="sheet-head">
          <span>答案溯源</span>
          <button class="sheet-close" @click="showSources = false">
            <Icon name="chevron-down" :size="18" />
          </button>
        </div>
        <div class="sheet-body">
          <SourcePanel @locate="onCite" @ask="send" />
        </div>
      </div>
    </div>

    <MobileNav v-model="tab" />
  </div>
</template>

<style scoped>
.mwb {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-page);
  position: relative;
  overflow: hidden;
}
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 35;
}
.mtop {
  height: var(--mobile-topbar-h);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}
.menu {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-pill);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-primary);
}
.brand {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
}
.actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}
.account {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-pill);
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 13px;
}
.scroll {
  flex: 1;
  overflow-y: auto;
  padding: 20px 20px calc(90px + env(safe-area-inset-bottom));
}
.scroll.center {
  display: flex;
  align-items: center;
  justify-content: center;
}
.empty-me {
  text-align: center;
  color: var(--text-placeholder);
}
.empty-me p {
  margin-top: 8px;
  font-size: 13px;
}
.greet {
  margin-bottom: 14px;
}
.greet h2 {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 600;
}
.greet p {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.qcard {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 46px;
  padding: 0 6px 0 16px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  margin-bottom: 22px;
}
.qcard input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  color: var(--text-primary);
}
.qcard input::placeholder {
  color: var(--text-placeholder);
}
.qsend {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.sec-title {
  font-size: 13px;
  font-weight: 600;
  margin: 6px 0 12px;
}
.kb-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 8px;
}
.trend {
  list-style: none;
}
.trend li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  margin-bottom: 8px;
}
.rk {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.rk.top {
  background: var(--brand-soft);
  color: var(--brand);
}
.tq {
  flex: 1;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tf {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

/* 问答视图：顶栏 + 对话流 + 输入框，底部留出导航高度 */
.chat-view {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding-bottom: calc(62px + env(safe-area-inset-bottom));
}
.chat-bar {
  flex-shrink: 0;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
}
.chat-title {
  font-size: 14px;
  font-weight: 600;
}
.src-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 12px;
  border-radius: var(--radius-pill);
  background: var(--bg-subtle);
  color: var(--text-placeholder);
  font-size: 12px;
  font-weight: 500;
  transition: color 0.15s ease, background 0.15s ease;
}
.src-btn.on {
  background: var(--brand-soft);
  color: var(--brand);
}
.src-btn:disabled {
  opacity: 0.5;
}
/* ChatStream 在移动端铺满，内部滚动 */
.chat-flex {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.m-composer {
  flex-shrink: 0;
}

/* 溯源底部弹层 */
.sheet-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 40;
  display: flex;
  align-items: flex-end;
  animation: fade 0.2s ease;
}
.sheet {
  width: 100%;
  max-height: 78%;
  background: var(--bg-page);
  border-radius: 16px 16px 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: sheetUp 0.26s cubic-bezier(0.16, 1, 0.3, 1);
}
.sheet-head {
  flex-shrink: 0;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px 0 18px;
  font-size: 14px;
  font-weight: 600;
  border-bottom: 1px solid var(--border);
}
.sheet-close {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-pill);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}
.sheet-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
/* 让桌面端 SourcePanel 在弹层里铺满 */
.sheet-body :deep(.panel) {
  width: 100%;
  min-width: 0;
  border-left: none;
  border-radius: 0;
  overflow: visible;
  padding: 16px;
}
@keyframes fade {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes sheetUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

/* tab 切换过渡：轻微上滑淡入，kb ↔ chat 等都顺 */
.tab-enter-active,
.tab-leave-active {
  transition: opacity 0.22s ease, transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  will-change: opacity, transform;
}
.tab-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.tab-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
