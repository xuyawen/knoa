<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import Icon from '@/components/Icon.vue'
import { createKnowledgeBase } from '@/api'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useSidebarCollapsed } from '@/composables/useSidebarCollapsed'

const { collapsed } = useSidebarCollapsed()

function onCollapse() {
  collapsed.value = true
}

function onExpand() {
  collapsed.value = false
}

// 接真实 KB 列表（含实时"待复核"角标），来自 /api/knowledge-bases
const knowledgeStore = useKnowledgeStore()
const knowledgeBases = computed(() => knowledgeStore.bases)

onMounted(() => knowledgeStore.load())

// ── 新增知识库弹窗 ──
const showCreate = ref(false)
const creating = ref(false)
const createError = ref<string | null>(null)
const newName = ref('')
const newDesc = ref('')
const newIcon = ref('library')
const ICON_OPTIONS = [
  'library', 'compliance', 'ads', 'logistics', 'selection',
  'service', 'graph', 'bell', 'search', 'users',
]

function openCreate() {
  newName.value = ''
  newDesc.value = ''
  newIcon.value = 'library'
  createError.value = null
  showCreate.value = true
}

function closeCreate() {
  showCreate.value = false
}

async function submitCreate() {
  const name = newName.value.trim()
  if (!name) {
    createError.value = '请填写知识库名称'
    return
  }
  creating.value = true
  createError.value = null
  try {
    await createKnowledgeBase({ name, icon: newIcon.value, description: newDesc.value.trim() || null })
    await knowledgeStore.reload() // 新建后强制刷新列表（绕过 loaded 缓存）
    closeCreate()
  } catch (e) {
    createError.value = e instanceof Error ? e.message : String(e)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div class="kb-page">
    <AppSidebar :collapsed="collapsed" @collapse="onCollapse" @expand="onExpand" />
    <div class="main">
      <TopBar title="知识库" />
      <div class="body">
        <!-- 操作栏：新增菜单级知识库 -->
        <div class="toolbar">
          <h1 class="page-title">文档管理</h1>
          <button class="btn-primary" @click="openCreate">
            <Icon name="plus" :size="16" />
            新增知识库
          </button>
        </div>

        <div class="kb-list">
          <router-link
            v-for="kb in knowledgeBases"
            :key="kb.id"
            :to="'/knowledge-bases/' + kb.id"
            class="kb-item"
          >
            <span class="kb-icon"><Icon :name="kb.icon" :size="20" /></span>
            <span class="kb-name">{{ kb.name }}</span>
            <span v-if="kb.badge" class="kb-badge" :class="kb.badgeType">{{ kb.badge }}</span>
          </router-link>

          <div v-if="!knowledgeBases.length" class="empty-state">
            <Icon name="inbox" :size="36" />
            <p>暂无知识库，点击右上角「新增知识库」创建</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 新增知识库弹窗 -->
    <div v-if="showCreate" class="modal-mask" @click.self="closeCreate">
      <div class="modal">
        <div class="modal-head">
          <h3>新增知识库</h3>
          <button class="modal-close" @click="closeCreate"><Icon name="plus" :size="16" style="transform: rotate(45deg)" /></button>
        </div>

        <label class="field">
          <span class="field-label">名称 <em>*</em></span>
          <input v-model="newName" type="text" placeholder="如：合规管理 / 广告运营" class="input" />
        </label>

        <label class="field">
          <span class="field-label">图标</span>
          <div class="icon-grid">
            <button
              v-for="ic in ICON_OPTIONS"
              :key="ic"
              type="button"
              class="icon-opt"
              :class="{ active: newIcon === ic }"
              @click="newIcon = ic"
            >
              <Icon :name="ic" :size="20" />
            </button>
          </div>
        </label>

        <label class="field">
          <span class="field-label">描述</span>
          <textarea v-model="newDesc" rows="3" placeholder="这个知识库用来存什么（可选）" class="input" />
        </label>

        <p v-if="createError" class="create-error">{{ createError }}</p>

        <div class="modal-foot">
          <button class="btn-ghost" @click="closeCreate">取消</button>
          <button class="btn-primary" :disabled="creating" @click="submitCreate">
            {{ creating ? '创建中…' : '创建' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kb-page {
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

/* 操作栏 */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
}
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  background: var(--brand);
  color: #fff;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  transition: background 0.15s ease, transform 0.15s ease;
}
.btn-primary:hover {
  background: var(--brand-hover);
  transform: translateY(-1px);
}
.btn-primary:disabled {
  opacity: 0.7;
  cursor: default;
  transform: none;
}

.kb-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}
.kb-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--text-primary);
  text-align: left;
  text-decoration: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}
.kb-item:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-card);
  transform: translateY(-1px);
}
.kb-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--bg-subtle);
  color: var(--text-secondary);
  flex-shrink: 0;
}
.kb-name {
  font-weight: 500;
  flex: 1;
}
.kb-badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  white-space: nowrap;
  flex-shrink: 0;
}
.kb-badge.danger {
  background: var(--danger-soft);
  color: var(--danger);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 0;
  color: var(--text-placeholder);
}
.empty-state p {
  font-size: 14px;
}

/* 弹窗 */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 60;
}
.modal {
  width: 440px;
  max-width: calc(100vw - 32px);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-float);
  padding: 22px 22px 18px;
}
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.modal-head h3 {
  font-size: 16px;
  font-weight: 600;
}
.modal-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  transition: background 0.15s ease;
}
.modal-close:hover {
  background: var(--bg-subtle);
}
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-bottom: 14px;
}
.field-label {
  font-size: 13px;
  color: var(--text-secondary);
}
.field-label em {
  color: var(--danger);
  font-style: normal;
}
.input {
  width: 100%;
  padding: 9px 12px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  outline: none;
  font-family: inherit;
  resize: vertical;
  transition: border-color 0.15s ease;
}
.input:focus {
  border-color: var(--brand);
}
.icon-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}
.icon-opt {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
}
.icon-opt:hover {
  border-color: var(--brand);
}
.icon-opt.active {
  border-color: var(--brand);
  color: var(--brand);
  background: var(--brand-soft);
}
.create-error {
  margin: -4px 0 12px;
  font-size: 12px;
  color: var(--danger);
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}
.btn-ghost {
  padding: 9px 18px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  transition: background 0.15s ease;
}
.btn-ghost:hover {
  background: var(--bg-subtle);
}

@media (max-width: 900px) {
  .body {
    padding: 16px;
  }
}
</style>
