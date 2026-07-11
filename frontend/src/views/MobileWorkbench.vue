<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  knowledgeBases,
  workspaceEntries,
  health,
  messages,
  trending,
} from '@/mocks/data'
import AppSidebar from '@/components/AppSidebar.vue'
import Icon from '@/components/Icon.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import KnowledgeCard from '@/components/KnowledgeCard.vue'
import MobileNav from '@/components/MobileNav.vue'

const drawer = ref(false)
const question = ref('')

const answer = computed(() => messages.find((m) => m.role === 'assistant'))

const kbCards = computed(() => {
  const fromKb = knowledgeBases.map((k) => {
    const h = health.find((x) => x.kb === k.name)
    return {
      icon: k.icon,
      name: k.name,
      alert: k.id === 'compliance',
      meta: h ? `${h.docCount} 篇 · ${Math.round(h.coverage * 100)}% 覆盖` : '',
    }
  })
  const fromWs = workspaceEntries.slice(0, 1).map((e) => ({
    icon: 'library',
    name: e,
    alert: false,
    meta: '快捷入口',
  }))
  return [...fromKb, ...fromWs]
})

function submit() {
  if (!question.value.trim()) return
  console.log('ask:', question.value)
  question.value = ''
}
</script>

<template>
  <div class="mwb">
    <!-- 抽屉侧栏 -->
    <AppSidebar :mobile-open="drawer" :active-base="'compliance'" @close="drawer = false" />
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

    <!-- 滚动内容 -->
    <main class="scroll">
      <!-- 问候 + 提问卡 -->
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

      <!-- 知识库网格 -->
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

      <!-- 答案溯源预览 -->
      <div class="sec-title">答案溯源</div>
      <div class="answer-card" v-if="answer">
        <div class="a-head">
          <span class="a-avatar"><Icon name="sparkle" :size="14" /></span>
          <span class="a-name">知海 · 运营知识助手</span>
          <span class="a-tag">RAG 溯源</span>
        </div>
        <p class="a-body">{{ answer.content }}</p>
        <div class="a-cites">
          <span v-for="c in answer.citations" :key="c" class="cite">[{{ c }}]</span>
          <span class="more">查看完整回答 ›</span>
        </div>
      </div>

      <!-- 今日高频 -->
      <div class="sec-title">今日高频</div>
      <ul class="trend">
        <li v-for="(t, i) in trending" :key="i">
          <span class="rk" :class="{ top: i < 3 }">{{ i + 1 }}</span>
          <span class="tq">{{ t.question }}</span>
          <span class="tf"><Icon name="fire" :size="13" />{{ t.count }}</span>
        </li>
      </ul>
    </main>

    <MobileNav />
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
.answer-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px;
  box-shadow: var(--shadow-card);
  margin-bottom: 8px;
}
.a-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.a-avatar {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.a-name {
  font-size: 13px;
  font-weight: 600;
}
.a-tag {
  margin-left: auto;
  font-size: 11px;
  color: var(--brand);
  background: var(--chip-soft);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
}
.a-body {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.a-cites {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.cite {
  font-size: 12px;
  font-weight: 600;
  color: var(--brand);
  background: var(--chip-soft);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
}
.more {
  font-size: 12px;
  color: var(--text-placeholder);
  margin-left: auto;
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
</style>
