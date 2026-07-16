<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import AppSidebar from '@/components/AppSidebar.vue'
import Icon from '@/components/Icon.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import KnowledgeCard from '@/components/KnowledgeCard.vue'
import MobileNav from '@/components/MobileNav.vue'
import ChatStream from '@/components/ChatStream.vue'
import Composer from '@/components/Composer.vue'
import SourcePanel from '@/components/SourcePanel.vue'
import type { ChatAttachment } from '@/types/api'

const knowledge = useKnowledgeStore()
const chat = useChatStore()
const auth = useAuthStore()
const router = useRouter()

const drawer = ref(false)
const tab = ref('home')
const question = ref('')
const showSources = ref(false)
const kbDropdownOpen = ref(false)

const sourceCount = computed(() => chat.sources.length)

const kbLabel = computed(() => {
  if (!chat.filterKb) return '全部知识库'
  const kb = knowledge.bases.find(b => b.id === chat.filterKb)
  return kb?.name || '全部知识库'
})

const roleLabel = computed(() => {
  const r = auth.user?.role
  if (r === 'admin') return '管理员'
  if (r === 'editor') return '编辑'
  if (r === 'viewer') return '访客'
  return r || ''
})

const initial = computed(() => (auth.user?.displayName || auth.user?.username || '?').charAt(0))

const greeting = computed(() => {
  const name = auth.user?.displayName || auth.user?.username || ''
  return name ? `你好，${name}` : '你好'
})

const joinedAt = computed(() => {
  const s = auth.user?.createdAt
  if (!s) return ''
  return new Date(s).toLocaleDateString('zh-CN')
})

async function submit() {
  const q = question.value.trim()
  if (!q) return
  question.value = ''
  await knowledge.load()
  send({ text: q, files: [] })
}

function onLogout() {
  auth.logout()
  router.replace('/login')
}

function onCardSelect(id: string | null) {
  if (id) {
    knowledge.selectBase(id)
    tab.value = 'chat'
  } else {
    // "文档管理"等无 id 的快捷入口 → 跳知识库管理列表
    router.push('/knowledge-bases')
  }
}

function send(payload: { text: string; files: ChatAttachment[] }) {
  chat.ask(payload.text, knowledge.activeBase, payload.files)
  tab.value = 'chat'
  showSources.value = false
}

// 溯源卡片「追问」：纯文本，无附件
function onAsk(q: string) {
  chat.ask(q, knowledge.activeBase)
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
      id: kb.id,
      name: kb.name,
      alert: kb.badge?.includes('待复核'),
      meta: h ? `${h.docCount} 篇 · 健康 ${Math.round(h.healthScore * 100)}%` : '',
      healthScore: h ? h.healthScore : 0,
    }
  })
  const fromWs = ['文档管理'].map(e => ({
    id: null,
    name: e,
    alert: false,
    meta: '快捷入口',
    healthScore: undefined as number | undefined,
  }))
  return [...fromKb, ...fromWs]
})

onMounted(() => {
  document.addEventListener('click', (e: MouseEvent) => {
    const t = e.target as HTMLElement
    if (!t.closest('.kb-dropdown')) kbDropdownOpen.value = false
  })
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
        <button class="m-new" @click="chat.startNewChat()" title="新建对话">
          <Icon name="plus" :size="20" />
        </button>
        <ThemeToggle />
        <div class="account">{{ initial }}</div>
      </div>
    </header>

    <!-- 内容区：tab 切换带过渡（kb ↔ chat 等） -->
    <Transition name="tab" mode="out-in">
      <div
        class="pane"
        :class="{
          scroll: tab === 'home' || tab === 'kb' || tab === 'me',
          'chat-view': tab === 'chat',
        }"
        :key="tab"
      >
        <!-- 首页 -->
        <template v-if="tab === 'home'">
          <div class="greet">
            <h2>{{ greeting }}</h2>
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
              :id="c.id"
              :name="c.name"
              :meta="c.meta"
              :alert="c.alert"
              :healthScore="c.healthScore"
              @select="onCardSelect"
            />
          </div>

          <div class="sec-title">今日高频</div>
          <ul class="trend">
            <li v-for="(t, i) in knowledge.trending" :key="i">
              <span class="rk" :class="{ top: i < 3 }">{{ i + 1 }}</span>
              <span class="tq">{{ t.question }}</span>
              <span class="tf">{{ t.count }}</span>
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
              :id="c.id"
              :name="c.name"
              :meta="c.meta"
              :alert="c.alert"
              :healthScore="c.healthScore"
              @select="onCardSelect"
            />
          </div>
        </template>

        <!-- 问答 -->
        <template v-else-if="tab === 'chat'">
          <div class="chat-bar">
            <!-- 知识库下拉 -->
            <div class="kb-dropdown" :class="{ open: kbDropdownOpen }">
              <button type="button" class="kb-trigger" @click="kbDropdownOpen = !kbDropdownOpen">
                <span>{{ kbLabel }}</span>
                <Icon name="chevron-down" :size="14" />
              </button>
              <transition name="dropdown">
                <ul v-if="kbDropdownOpen" class="kb-menu">
                  <li
                    :class="{ active: !chat.filterKb }"
                    @click="chat.filterKb = null; kbDropdownOpen = false"
                  >全部知识库</li>
                  <li
                    v-for="kb in knowledge.bases"
                    :key="kb.id"
                    :class="{ active: chat.filterKb === kb.id }"
                    @click="chat.filterKb = kb.id; kbDropdownOpen = false"
                  >{{ kb.name }}</li>
                </ul>
              </transition>
            </div>

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

          <ChatStream class="chat-flex" :hide-filter="true" @cite="onCite" />

          <Composer class="m-composer" @send="send" />
        </template>

        <!-- 我的 -->
        <template v-else>
          <div class="profile">
            <div class="pf-head">
              <div class="pf-avatar">{{ initial }}</div>
              <div class="pf-id">
                <div class="pf-name">{{ auth.user?.displayName || auth.user?.username }}</div>
                <div class="pf-role">{{ roleLabel }}</div>
              </div>
            </div>

            <div class="pf-stats">
              <div class="stat">
                <span class="stat-num">{{ knowledge.bases.length }}</span>
                <span class="stat-label">知识库</span>
              </div>
              <div class="stat">
                <span class="stat-num">{{ knowledge.bases.reduce((s, kb) => s + (kb.pendingCount || 0), 0) }}</span>
                <span class="stat-label">需复核</span>
              </div>
            </div>

            <div class="pf-list">
              <div class="pf-row">
                <span class="pf-k">用户名</span>
                <span class="pf-v">{{ auth.user?.username }}</span>
              </div>
              <div class="pf-row">
                <span class="pf-k">角色</span>
                <span class="pf-v">{{ roleLabel }}</span>
              </div>
              <div class="pf-row" v-if="joinedAt">
                <span class="pf-k">加入时间</span>
                <span class="pf-v">{{ joinedAt }}</span>
              </div>
            </div>

            <button class="pf-logout" @click="onLogout">
              <Icon name="logout" :size="16" />
              <span>退出登录</span>
            </button>
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
          <SourcePanel @locate="onCite" @ask="onAsk" />
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
  padding: 0 12px;
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
.m-new {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-pill);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-primary);
  transition: background 0.15s ease;
}
.m-new:active {
  background: var(--bg-subtle);
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
  padding: 12px 12px calc(90px + env(safe-area-inset-bottom));
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
.profile {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.pf-head {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}
.pf-avatar {
  width: 52px;
  height: 52px;
  flex-shrink: 0;
  border-radius: var(--radius-pill);
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 600;
}
.pf-id {
  min-width: 0;
}
.pf-name {
  font-size: 17px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pf-role {
  margin-top: 3px;
  font-size: 12px;
  color: var(--brand);
  background: var(--brand-soft);
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-weight: 500;
}
.pf-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 18px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.stat-num {
  font-size: 22px;
  font-weight: 700;
  font-family: var(--font-display);
}
.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
}
.pf-list {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.pf-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  font-size: 14px;
}
.pf-row + .pf-row {
  border-top: 1px solid var(--border);
}
.pf-k {
  color: var(--text-secondary);
}
.pf-v {
  color: var(--text-primary);
  font-weight: 500;
}
.pf-logout {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 48px;
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  border: 1px solid var(--danger-soft, #f3c0c0);
  color: var(--danger, #e5484d);
  font-size: 14px;
  font-weight: 500;
  transition: background 0.15s ease;
  margin-top: 4px;
}
.pf-logout:hover {
  background: var(--danger-soft, #fde8e8);
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
/* 移动端知识库下拉（chat-bar 内） */
.kb-dropdown {
  position: relative;
  flex: 1;
  min-width: 0;
}
.kb-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 32px;
  padding: 0 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.kb-trigger:hover { border-color: var(--brand); }
.kb-dropdown.open .kb-trigger {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(59,130,246,0.12);
}
.kb-dropdown.open .kb-trigger svg { transform: rotate(180deg); }
.kb-trigger svg { transition: transform 0.2s; flex-shrink: 0; }
.kb-menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 25;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 16px rgba(0,0,0,0.10);
  padding: 4px 0;
  list-style: none;
  max-height: 220px;
  overflow-y: auto;
}
.kb-menu li {
  padding: 8px 14px;
  font-size: 14px;
  color: var(--text-primary);
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: background 0.12s, color 0.12s;
}
.kb-menu li:hover { background: var(--bg-subtle); }
.kb-menu li.active { color: var(--brand); font-weight: 600; }
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

/* 下拉菜单过渡 */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
