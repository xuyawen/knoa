<script setup lang="ts">
// AI 智能问答 — 按 640(5).png 截图 1:1 还原。
defineProps<{ activeTab?: number }>()

import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'

const inputText = ref('')
const suggested = ref(['差旅报销需要哪些材料?', '差额申请提交多久能到账?', '差旅报销的标准是怎么样的?', '特殊情况如何申请超额报销?'])

const conversations = [
  { q: '公司差旅报销政策是什么？', preview: '想跟公司（发票费用报销管理办法）…', time: '10:30', active: true },
  { q: '如何申请系统权限？', preview: '您可以通过以下步骤申请系统权限：…', time: '昨天' },
  { q: '员工入职流程是怎样的？', preview: '员工入职流程主要包括以下几个步骤：…', time: '昨天' },
  { q: '项目管理规范有哪些？', preview: '公司项目管理规范主要内容包括以下方面：…', time: '05/20' },
  { q: '信息安全管理制原则解读', preview: '信息安全管理制原则主要包括以下几个方面：…', time: '05/19' },
  { q: '如何提交IT支持工单？', preview: '您可以通过以下方式提交IT支持工单：…', time: '05/18' },
  { q: '年度绩效考核标准是什么？', preview: '年度绩效考核标准主要包括以下维度：…', time: '05/17' },
]

const refs = [
  { name: '企业差旅报销管理办法.docx', size: '68.5 KB', type: 'doc', color: '#3B82F6', date: '2024-01-15' },
  { name: '差旅报销标准图表.pdf', size: '196.7 KB', type: 'pdf', color: '#EF4444', date: '2024-01-15' },
  { name: '各城市住宿标准.xlsx', size: '33.4 KB', type: 'excel', color: '#10B981', date: '2024-01-15' },
]

function pick(s: string) {
  inputText.value = s
}
function refreshSuggested() {
  suggested.value = [...suggested.value].reverse()
}
</script>

<template>
  <div class="chat-page">
    <!-- ====== 左栏：会话列表 ====== -->
    <aside class="chat-sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">会话列表</span>
        <Icon name="list" :size="16" class="sidebar-icon-btn" />
      </div>
      <button class="btn btn-new-chat">
        <Icon name="plus" :size="14" /> 新建对话
      </button>
      <div class="conv-list">
        <div v-for="(c, i) in conversations" :key="i" class="conv-item" :class="{ active: c.active }">
          <div class="conv-q">{{ c.q }}</div>
          <div class="conv-preview">{{ c.preview }}</div>
          <div class="conv-time">{{ c.time }}</div>
        </div>
      </div>
      <button class="show-more">查看更多会话 <Icon name="chevron-down" :size="11" /></button>
    </aside>

    <!-- ====== 中栏：对话区 ====== -->
    <main class="chat-main">
      <!-- 对话头部 -->
      <div class="chat-header">
        <h3 class="chat-question">公司差旅报销政策是什么？</h3>
        <button class="btn-clear-chat"><Icon name="close" :size="13" /> 清空对话</button>
      </div>

      <!-- 消息区 -->
      <div class="messages-area">
        <!-- AI 回复气泡 -->
        <div class="msg-row ai-msg">
          <div class="msg-avatar ai-avatar">
            <Icon name="chat" :size="16" />
          </div>
          <div class="msg-bubble">
            <ol class="answer-list">
              <li><strong>适用范围：</strong>适用于公司所有因公出差的员工。</li>
              <li><strong>报销标准：</strong>交通费按公司标准执行，住宿费按城市级别设定上限，餐饮费每天不超过100元标准；</li>
              <li><strong>报销流程：</strong>出差结束后5个工作日内提交报销申请，需附完整票据及出差审批单；</li>
              <li><strong>资质要求：</strong>所有票据需真实有效，不得涂改，电子票据需打印并加盖公章；</li>
              <li><strong>其他说明：</strong>特殊情况需超标报销的，需提前申请并经部门负责人审批。</li>
            </ol>
            <p class="answer-note">具体细则请参考以下文档，如有疑问可联系财务部（内线：8123）。</p>
          </div>
        </div>
        <!-- 引用文档 -->
        <div class="refs-section">
          <div class="refs-label">引用文档 (3)</div>
          <div class="refs-list">
            <div v-for="(r, i) in refs" :key="i" class="ref-card card">
              <div class="ref-icon" :style="{ background: r.color + '18', color: r.color }">
                <Icon :name="r.type === 'pdf' ? 'pdf' : r.type === 'excel' ? 'excel' : 'doc'" :size="18" />
              </div>
              <div class="ref-info">
                <div class="ref-name">{{ r.name }}</div>
                <div class="ref-meta">{{ r.size }} · 筛选 · {{ r.date }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 建议追问 -->
      <div class="suggest-row">
        <span class="suggest-label">你可能还想问</span>
        <button v-for="(s, i) in suggested" :key="i" class="chip" @click="pick(s)">{{ s }}</button>
        <button class="chip ghost" @click="refreshSuggested"><Icon name="refresh" :size="13" />换一批</button>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <textarea
          v-model="inputText"
          placeholder="请输入问题，Shift + Enter 换行"
          rows="2"
          class="chat-input"
        ></textarea>
        <div class="input-bar">
          <span class="char-count">{{ inputText.length }} / 2000</span>
          <div class="input-actions">
            <button class="attach-btn" title="附件"><Icon name="attach" :size="17" /></button>
            <button class="btn btn-primary send-btn" :disabled="!inputText.trim()">
              <Icon name="send" :size="15" /> 发送
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  gap: 0;
  height: calc(100vh - 58px - 48px); /* 减去顶栏和 padding */
  min-height: 520px;
}

/* ---- 会话侧栏 ---- */
.chat-sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg-surface);
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 16px 12px;
}
.sidebar-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}
.sidebar-icon-btn { color: var(--text-tertiary); cursor: pointer; }

.btn-new-chat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: calc(100% - 24px);
  margin: 0 auto 10px;
  height: 36px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  font-size: 13px;
  font-weight: 500;
  color: var(--brand);
  cursor: pointer;
  font-family: inherit;
  transition: all var(--dur-fast);
}
.btn-new-chat:hover { border-color: var(--brand); background: var(--brand-soft); }

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}
.conv-item {
  padding: 11px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--dur-fast);
  border-left: 3px solid transparent;
  margin-bottom: 2px;
}
.conv-item:hover { background: var(--bg-hover); }
.conv-item.active {
  background: var(--brand-soft);
  border-left-color: var(--brand);
}
.conv-q {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.35;
  margin-bottom: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-preview {
  font-size: 12px;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 2px;
}
.conv-time {
  font-size: 11px;
  color: var(--text-placeholder);
}

.show-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 10px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--brand);
  cursor: pointer;
  background: transparent;
  font-family: inherit;
}
.show-more:hover { opacity: 0.75; }

/* ---- 对话主区 ---- */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border);
}
.chat-question {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}
.btn-clear-chat {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
}
.btn-clear-chat:hover { background: var(--bg-hover); }

/* ---- 消息区 ---- */
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.msg-row {
  display: flex;
  gap: 12px;
  max-width: 800px;
}
.msg-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
  margin-top: 3px;
}
.ai-avatar { background: var(--brand); }
.msg-bubble {
  flex: 1;
  padding: 14px 18px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 0 var(--radius-lg) var(--radius-lg) var(--radius-lg);
  box-shadow: var(--shadow-card);
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--text-primary);
}

.answer-list {
  margin: 0 0 10px;
  padding-left: 18px;
}
.answer-list li { margin-bottom: 6px; }
.answer-note {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}

/* ---- 引用文档 ---- */
.refs-section {
  margin-top: 16px;
  max-width: 800px;
}
.refs-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
.refs-list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.ref-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  transition: box-shadow var(--dur-fast), transform var(--dur-fast);
}
.ref-card:hover {
  box-shadow: var(--shadow-float);
  transform: translateY(-1px);
}
.ref-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ref-info { min-width: 0; }
.ref-name {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ref-meta {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

/* ---- 建议追问 ---- */
.suggest-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px 8px;
  flex-wrap: wrap;
}
.suggest-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
}
.chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 13px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-surface);
  cursor: pointer;
  transition: all var(--dur-fast);
  white-space: nowrap;
  font-family: inherit;
}
.chip:hover { border-color: var(--brand); color: var(--brand); background: var(--brand-soft); }
.chip.ghost {
  border-style: dashed;
  color: var(--text-tertiary);
  background: transparent;
}
.chip.ghost:hover { color: var(--brand); border-color: var(--brand); }

/* ---- 输入区 ---- */
.input-area {
  padding: 12px 24px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-surface);
}
.chat-input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  font-size: 14px;
  resize: none;
  outline: none;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color var(--dur-fast), box-shadow var(--dur-fast);
}
.chat-input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.chat-input::placeholder { color: var(--text-placeholder); }

.input-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.char-count {
  font-size: 12px;
  color: var(--text-tertiary);
}
.input-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.attach-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  background: transparent;
  transition: all var(--dur-fast);
}
.attach-btn:hover { background: var(--bg-hover); color: var(--text-primary); }

.send-btn { height: 36px; padding: 0 20px; font-size: 13px; }
</style>
