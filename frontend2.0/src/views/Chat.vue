<script setup lang="ts">
// AI 智能问答（对应截图 #5）：会话列表 + 对话区 + 引用文档卡片 + 建议追问。
// 界面壳阶段：静态示例数据，未接后端 SSE。
import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'

const sessions = [
  { id: 1, title: '如何申请数据权限？', time: '09:40', active: true },
  { id: 2, title: '产品手册里的部署流程', time: '昨天' },
  { id: 3, title: 'Q3 培训重点梳理', time: '周一' },
]
const activeId = ref(1)

const messages = [
  { role: 'user', text: '公司数据安全管理制度里，对外共享数据有哪些要求？' },
  {
    role: 'ai',
    text: '根据《2026 数据安全管理制度》与《个人信息保护实施细则》，对外共享数据需满足以下要求：\n\n1. 分级审批：机密级数据对外共享须经安全负责人批准；\n2. 最小必要：仅共享业务必需字段，敏感字段须脱敏；\n3. 协议约束：与接收方签订数据保护协议并明确用途；\n4. 审计留痕：共享行为记入审计日志，保留不少于 3 年。',
    citations: [
      { title: '2026 数据安全管理制度', from: '安全管理制度 › 数据安全' },
      { title: '个人信息保护实施细则', from: '规章制度 › 合规' },
    ],
  },
]

const suggested = ['对外共享的审批流程具体怎么走？', '数据分级有哪几类？', '审计日志保留多久？']
const input = ref('')

function send() {
  if (!input.value.trim()) return
  input.value = ''
}
function pick(s: string) {
  input.value = s
}
</script>

<template>
  <div class="chat fade-up">
    <!-- 会话列表 -->
    <aside class="chat-side card">
      <div class="chat-side-head">
        <button class="btn btn-primary btn-sm" style="flex: 1"><Icon name="plus" :size="15" />新建对话</button>
      </div>
      <div class="chat-side-list">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="sess"
          :class="{ on: s.id === activeId }"
          @click="activeId = s.id"
        >
          <Icon name="chat" :size="15" class="sess-ic" />
          <div class="sess-meta">
            <div class="sess-title truncate">{{ s.title }}</div>
            <div class="sess-time">{{ s.time }}</div>
          </div>
        </div>
      </div>
      <div class="divider" />
      <div class="chat-side-foot">
        <div class="nav-item"><Icon name="chat" :size="16" /><span>历史会话</span></div>
        <div class="nav-item"><Icon name="doc" :size="16" /><span>问答记录</span></div>
        <div class="nav-item"><Icon name="settings" :size="16" /><span>模型配置</span></div>
      </div>
    </aside>

    <!-- 对话区 -->
    <section class="chat-main">
      <div class="chat-scroll">
        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <div class="bubble">
            <p v-for="(line, li) in m.text.split('\n')" :key="li">{{ line || ' ' }}</p>

            <div v-if="m.citations" class="cites">
              <div v-for="(c, ci) in m.citations" :key="ci" class="cite">
                <Icon name="doc" :size="14" class="cite-ic" />
                <div class="cite-body">
                  <div class="cite-title">{{ c.title }}</div>
                  <div class="cite-from">{{ c.from }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 建议追问 -->
      <div class="suggest">
        <span class="suggest-label">你可能还想问</span>
        <button v-for="(s, i) in suggested" :key="i" class="chip" @click="pick(s)">{{ s }}</button>
        <button class="chip ghost" @click="pick('换一批示例问题')"><Icon name="refresh" :size="13" />换一批</button>
      </div>

      <!-- 输入 -->
      <div class="composer">
        <button class="icon-btn" title="附件"><Icon name="plus" :size="18" /></button>
        <input v-model="input" class="input bare" placeholder="输入你的问题…（0 / 2000）" @keyup.enter="send" />
        <button class="btn btn-primary" :disabled="!input.trim()" @click="send">发送</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.chat {
  display: grid;
  grid-template-columns: 264px 1fr;
  gap: 16px;
  height: calc(100vh - var(--topbar-h) - 48px);
}
.chat-side {
  display: flex;
  flex-direction: column;
  padding: 14px;
  overflow: hidden;
}
.chat-side-head { margin-bottom: 12px; }
.chat-side-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.sess {
  display: flex;
  gap: 10px;
  padding: 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--dur-fast);
}
.sess:hover { background: var(--bg-hover); }
.sess.on { background: var(--brand-soft); }
.sess-ic { color: var(--text-tertiary); margin-top: 2px; flex-shrink: 0; }
.sess.on .sess-ic { color: var(--brand); }
.sess-meta { min-width: 0; }
.sess-title { font-size: 13px; color: var(--text-primary); }
.sess-time { font-size: 11px; color: var(--text-tertiary); margin-top: 2px; }
.chat-side-foot { padding-top: 8px; }
.chat-side-foot .nav-item { margin-bottom: 2px; }

.chat-main {
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.chat-scroll { flex: 1; overflow-y: auto; padding: 22px; display: flex; flex-direction: column; gap: 16px; }
.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.bubble {
  max-width: 78%;
  padding: 13px 16px;
  border-radius: var(--radius-lg);
  font-size: 14px;
  line-height: 1.7;
}
.msg.user .bubble { background: var(--brand); color: #fff; border-bottom-right-radius: var(--radius-sm); }
.msg.ai .bubble { background: var(--bg-subtle); border: 1px solid var(--border); border-bottom-left-radius: var(--radius-sm); }
.bubble p { margin: 0 0 4px; }
.bubble p:last-child { margin-bottom: 0; }

.cites { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
.cite {
  display: flex;
  gap: 9px;
  padding: 9px 11px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.cite-ic { color: var(--brand); margin-top: 2px; flex-shrink: 0; }
.cite-title { font-size: 13px; font-weight: 600; }
.cite-from { font-size: 11px; color: var(--text-tertiary); margin-top: 1px; }

.suggest {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 14px 22px 0;
}
.suggest-label { font-size: 12px; color: var(--text-tertiary); margin-right: 2px; }
.chip {
  padding: 5px 13px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  background: var(--brand-soft);
  color: var(--brand);
  cursor: pointer;
  transition: all var(--dur-fast);
}
.chip:hover { background: var(--brand-ring); }
.chip.ghost { display: inline-flex; align-items: center; gap: 5px; background: var(--bg-subtle); color: var(--text-secondary); }

.composer {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-top: 1px solid var(--border);
}
.input.bare { border: none; background: transparent; height: 38px; }
.input.bare:focus { box-shadow: none; }

@media (max-width: 860px) {
  .chat { grid-template-columns: 1fr; }
  .chat-side { display: none; }
}
</style>
