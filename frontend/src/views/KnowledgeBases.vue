<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { KnowledgeBase } from '@/types/api'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import Icon from '@/components/Icon.vue'
import {
  batchDeleteKnowledgeBases,
  createKnowledgeBase,
  deleteKnowledgeBase,
  reorderKnowledgeBases,
  updateKnowledgeBase,
} from '@/api'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useSidebarCollapsed } from '@/composables/useSidebarCollapsed'

const { collapsed } = useSidebarCollapsed()
const router = useRouter()

function onCollapse() {
  collapsed.value = true
}
function onExpand() {
  collapsed.value = false
}

const isMobile = ref(false)
const drawer = ref(false)
let mq: MediaQueryList | undefined

function syncMobile() {
  isMobile.value = window.matchMedia('(max-width: 900px)').matches
}

// 接真实 KB 列表（含实时文档数 / 待复核角标），来自 /api/knowledge-bases
const knowledgeStore = useKnowledgeStore()
// 本地副本：拖拽时乐观更新顺序；store reload 后回同步到服务端真实顺序
const kbList = ref<KnowledgeBase[]>([])
watch(
  () => knowledgeStore.bases,
  (v) => {
    kbList.value = v.map((k) => ({ ...k }))
  },
  { immediate: true },
)
onMounted(() => {
  syncMobile()
  mq = window.matchMedia('(max-width: 900px)')
  mq.addEventListener('change', syncMobile)
  knowledgeStore.load()
})
onUnmounted(() => mq?.removeEventListener('change', syncMobile))

// ── 多选 ──
const selected = ref<Record<string, boolean>>({})
const selectedCount = computed(() => Object.values(selected.value).filter(Boolean).length)
const allSelected = computed({
  get: () => kbList.value.length > 0 && kbList.value.every((k) => selected.value[k.id]),
  set: (v: boolean) => {
    kbList.value.forEach((k) => {
      selected.value[k.id] = v
    })
  },
})
function onCheck(id: string, e: Event) {
  selected.value[id] = (e.target as HTMLInputElement).checked
}
function toggleAll(e: Event) {
  const v = (e.target as HTMLInputElement).checked
  kbList.value.forEach((k) => {
    selected.value[k.id] = v
  })
}

// ── 新增 / 编辑 弹窗（复用同一套 UI）──
const showCreate = ref(false)
const creating = ref(false)
const createError = ref<string | null>(null)
const editingId = ref<string | null>(null)
const newName = ref('')
const newDesc = ref('')

function openCreate() {
  editingId.value = null
  newName.value = ''
  newDesc.value = ''
  createError.value = null
  showCreate.value = true
}
function openEdit(kb: KnowledgeBase) {
  editingId.value = kb.id
  newName.value = kb.name
  newDesc.value = kb.description || ''
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
    if (editingId.value) {
      await updateKnowledgeBase(editingId.value, {
        name,
        description: newDesc.value.trim() || null,
      })
    } else {
      await createKnowledgeBase({
        name,
        description: newDesc.value.trim() || null,
      })
    }
    await knowledgeStore.reload() // 编辑/新建后强制刷新（绕过 loaded 缓存）
    closeCreate()
  } catch (e) {
    createError.value = e instanceof Error ? e.message : String(e)
  } finally {
    creating.value = false
  }
}

// ── 删除（单删 / 批量）二次确认 ──
const showDelConfirm = ref(false)
const delTarget = ref<{ ids: string[]; names: string[] }>({ ids: [], names: [] })
function askDeleteOne(kb: KnowledgeBase) {
  delTarget.value = { ids: [kb.id], names: [kb.name] }
  showDelConfirm.value = true
}
function askDeleteMany() {
  const picked = kbList.value.filter((k) => selected.value[k.id])
  if (!picked.length) return
  delTarget.value = {
    ids: picked.map((k) => k.id),
    names: picked.map((k) => k.name),
  }
  showDelConfirm.value = true
}
async function confirmDelete() {
  const ids = delTarget.value.ids
  try {
    if (ids.length === 1) {
      await deleteKnowledgeBase(ids[0])
    } else {
      await batchDeleteKnowledgeBases(ids)
    }
    selected.value = {}
    await knowledgeStore.reload()
    showDelConfirm.value = false
  } catch (e) {
    // 报错也关弹窗，保留列表让用户重试
    showDelConfirm.value = false
    console.error('delete knowledge base failed:', e)
  }
}

// ── 拖拽排序（原生 HTML5，不引入额外依赖）──
const dragIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)
function onDragStart(i: number, e: DragEvent) {
  dragIndex.value = i
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}
function onDragOver(i: number) {
  dragOverIndex.value = i
}
async function onDrop(i: number) {
  const from = dragIndex.value
  dragIndex.value = null
  dragOverIndex.value = null
  if (from === null || from === i) return
  const list = [...kbList.value]
  const [moved] = list.splice(from, 1)
  list.splice(i, 0, moved)
  kbList.value = list // 乐观更新
  try {
    await reorderKnowledgeBases(list.map((k) => k.id))
    await knowledgeStore.reload() // 以服务端顺序为准
  } catch (e) {
    await knowledgeStore.reload() // 失败回滚到服务端顺序
    console.error('reorder failed:', e)
  }
}

function goDetail(id: string) {
  router.push(`/knowledge-bases/${id}`)
}
</script>

<template>
  <div class="kb-page">
    <AppSidebar :collapsed="collapsed" :mobile-open="drawer" @collapse="onCollapse" @expand="onExpand" @close="drawer = false" />
    <div v-if="isMobile && drawer" class="overlay" @click="drawer = false" />

    <!-- 移动端顶栏 -->
    <header v-if="isMobile" class="m-top">
      <button class="m-menu" @click="drawer = true" title="菜单">
        <Icon name="menu" :size="20" />
      </button>
      <span class="m-title">文档管理</span>
      <button class="m-back" @click="router.push('/')">返回</button>
    </header>

    <div class="main">
      <TopBar v-if="!isMobile" title="知识库" />
      <div class="body">
        <!-- 操作栏 -->
        <div class="toolbar">
          <h1 class="page-title">文档管理</h1>
          <div class="toolbar-right">
            <button v-if="selectedCount > 0" class="btn-danger" @click="askDeleteMany">
              <Icon name="trash" :size="16" />
              批量删除 ({{ selectedCount }})
            </button>
            <button class="btn-primary" @click="openCreate">
              <Icon name="plus" :size="16" />
              新增知识库
            </button>
          </div>
        </div>

        <label v-if="kbList.length" class="select-all">
          <input type="checkbox" class="app-checkbox" :checked="allSelected" @change="toggleAll" />
          全选
        </label>

        <div class="kb-list">
          <div
            v-for="(kb, i) in kbList"
            :key="kb.id"
            class="kb-item"
            :class="{ 'drag-over': dragOverIndex === i }"
            draggable="true"
            @dragstart="onDragStart(i, $event)"
            @dragover.prevent="onDragOver(i)"
            @drop="onDrop(i)"
          >
            <span class="kb-drag" title="拖拽排序">⠿</span>
            <input
              type="checkbox"
              class="app-checkbox"
              :checked="!!selected[kb.id]"
              @click.stop
              @change="onCheck(kb.id, $event)"
            />
            <div class="kb-info">
              <span class="kb-name" @click="goDetail(kb.id)">{{ kb.name }}</span>
              <span class="kb-meta">{{ kb.documentCount }} 篇文档</span>
              <span v-if="kb.pendingCount > 0" class="kb-badge danger">{{ kb.pendingCount }} 待复核</span>
            </div>
            <span class="kb-actions">
              <button class="icon-btn" title="编辑" @click.stop="openEdit(kb)"><Icon name="edit" :size="16" /></button>
              <button class="icon-btn danger" title="删除" @click.stop="askDeleteOne(kb)"><Icon name="trash" :size="16" /></button>
            </span>
          </div>

          <div v-if="!kbList.length" class="empty-state">
            <Icon name="inbox" :size="36" />
            <p>暂无知识库，点击右上角「新增知识库」创建</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 新增 / 编辑 弹窗 -->
    <div v-if="showCreate" class="modal-mask" @click.self="closeCreate">
      <div class="modal">
        <div class="modal-head">
          <h3>{{ editingId ? '编辑知识库' : '新增知识库' }}</h3>
          <button class="modal-close" @click="closeCreate"><Icon name="plus" :size="16" style="transform: rotate(45deg)" /></button>
        </div>

        <label class="field">
          <span class="field-label">名称 <em>*</em></span>
          <input v-model="newName" type="text" placeholder="如：合规管理 / 广告运营" class="input" />
        </label>

        <label class="field">
          <span class="field-label">描述</span>
          <textarea v-model="newDesc" rows="3" placeholder="这个知识库用来存什么（可选）" class="input" />
        </label>
        <p v-if="createError" class="create-error">{{ createError }}</p>

        <div class="modal-foot">
          <button class="btn-ghost" @click="closeCreate">取消</button>
          <button class="btn-primary" :disabled="creating" @click="submitCreate">
            {{ creating ? '保存中…' : (editingId ? '保存' : '创建') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 删除二次确认 -->
    <div v-if="showDelConfirm" class="modal-mask" @click.self="showDelConfirm = false">
      <div class="modal modal-confirm">
        <div class="modal-head">
          <h3>确认删除</h3>
        </div>
        <p class="confirm-text">
          将删除以下 {{ delTarget.names.length }} 个知识库，及其下<strong>全部文档、向量与图谱数据</strong>，此操作不可恢复：
        </p>
        <ul class="confirm-list">
          <li v-for="n in delTarget.names" :key="n">{{ n }}</li>
        </ul>
        <div class="modal-foot">
          <button class="btn-ghost" @click="showDelConfirm = false">取消</button>
          <button class="btn-danger" @click="confirmDelete">确认删除</button>
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
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
}
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: var(--btn-padding-md);
  background: var(--brand);
  color: #fff;
  border-radius: var(--radius-md);
  font-size: var(--btn-font-size);
  font-weight: var(--btn-font-weight);
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
.btn-danger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: var(--btn-padding-md);
  height: var(--btn-height);
  background: #dc2626;
  color: #fff;
  border-radius: var(--radius-md);
  font-size: var(--btn-font-size);
  font-weight: var(--btn-font-weight);
  border: none;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}
.btn-danger:hover:not(:disabled) {
  background: #b91c1c;
}
.btn-danger:disabled {
  opacity: 0.4;
  cursor: default;
}

.select-all {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
  cursor: pointer;
  user-select: none;
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
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease, background 0.15s ease;
}
.kb-item:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-card);
  transform: translateY(-1px);
}
.kb-item.drag-over {
  border-color: var(--brand);
  background: var(--brand-soft);
}
.kb-drag {
  cursor: grab;
  color: var(--text-placeholder);
  font-size: 16px;
  line-height: 1;
  flex-shrink: 0;
  user-select: none;
}
.kb-drag:active {
  cursor: grabbing;
}
.kb-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.kb-name {
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
}
.kb-meta {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-subtle);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  white-space: nowrap;
  flex-shrink: 0;
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
.kb-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  flex-shrink: 0;
}
.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  transition: background 0.15s ease, color 0.15s ease;
}
.icon-btn:hover {
  background: var(--bg-subtle);
  color: var(--text-primary);
}
.icon-btn.danger:hover {
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
.modal-confirm {
  width: 420px;
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
.create-error {
  margin: -4px 0 12px;
  font-size: 12px;
  color: var(--danger);
}
.confirm-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 12px;
}
.confirm-list {
  list-style: none;
  margin: 0 0 16px;
  padding: 10px 12px;
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  max-height: 140px;
  overflow-y: auto;
}
.confirm-list li {
  font-size: 13px;
  color: var(--text-primary);
  padding: 3px 0;
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
  .main {
    padding-top: var(--mobile-topbar-h);
  }
  .body {
    padding: 16px;
  }
  .toolbar {
    flex-wrap: wrap; gap: 8px;
  }
  .page-title { font-size: 17px; }
  .kb-name { max-width: 180px; }
  .kb-actions { display: none; }
}

/* 移动端顶栏 */
.m-top {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: var(--mobile-topbar-h);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  z-index: 30;
}
.m-menu {
  width: 36px; height: 36px;
  border-radius: var(--radius-pill);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-primary);
}
.m-title {
  font-family: var(--font-display); font-size: 16px; font-weight: 600;
}
.m-back {
  margin-left: auto;
  font-size: 13px; color: var(--brand); font-weight: 500;
  background: none; border: none;
  cursor: pointer;
}
.overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 35;
}
</style>
