<script setup lang="ts">
// 记忆管理 — 个人中心下的长期记忆（Mem0 轻量版）列表 / 单条删除 / 清空。
// 写记忆发生在每次问答的后台任务里；本页只做「可读 / 可忘」。
import { ref, onMounted } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import RefreshButton from '@/components/ui/RefreshButton.vue'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { useAsyncAction } from '@/composables/useAsyncAction'
import { getMemories, deleteMemory, clearMemories } from '@/api'
import type { MemoryItem } from '@/types/api'

const toast = useToastStore()

const memories = ref<MemoryItem[]>([])
const loading = ref(false)

const deleteTarget = ref<MemoryItem | null>(null)
const showClearConfirm = ref(false)
const { busy: clearing, run: runClear } = useAsyncAction({ errorPrefix: '清空失败' })
const { busy: deletingMem, run: runDelete } = useAsyncAction({ errorPrefix: '删除失败' })

const TYPE_LABEL: Record<string, string> = {
  user_profile: '用户画像',
  preference: '偏好',
  fact: '事实',
  feedback: '反馈',
}
function typeLabel(t: string | null) {
  return (t && TYPE_LABEL[t]) || t || '其他'
}
// 类型色调用现有 accent token，避免写死颜色
const TYPE_TONE: Record<string, string> = {
  user_profile: 'brand',
  preference: 'violet',
  fact: 'green',
  feedback: 'amber',
}
function typeTone(t: string | null) {
  return (t && TYPE_TONE[t]) || 'brand'
}

function fmtTime(s: string | null) {
  if (!s) return '—'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadMemories(force = false) {
  loading.value = true
  try {
    memories.value = await getMemories(force)
  } catch (e: unknown) {
    memories.value = []
    toast.error(`加载记忆失败：${errMsg(e)}`)
  } finally {
    loading.value = false
  }
}

async function confirmDelete() {
  const target = deleteTarget.value
  if (!target) return
  await runDelete(async () => {
    await deleteMemory(target.id)
    memories.value = memories.value.filter((m) => m.id !== target.id)
    toast.success('已删除该条记忆')
  })
  deleteTarget.value = null
}

async function confirmClear() {
  await runClear(async () => {
    const n = await clearMemories()
    memories.value = []
    toast.success(`已清空 ${n} 条记忆`)
  })
  showClearConfirm.value = false
}

onMounted(loadMemories)
</script>

<template>
  <div class="mem-page fade-up">
    <div class="mem-head card">
      <div class="mem-head-left">
        <p class="mem-sub">系统会在问答过程中自动学习关于你的长期记忆（用户画像、偏好、关键事实等），你可以在此查看或遗忘。</p>
      </div>
      <div class="mem-actions">
        <RefreshButton :loading="loading" @click="loadMemories(true)" />
        <button
          class="btn btn-danger btn-sm"
          :disabled="!memories.length || clearing"
          @click="showClearConfirm = true"
        >
          <Icon name="trash" :size="13" /> 清空全部
        </button>
      </div>
    </div>

    <div class="card mem-body">
      <div v-if="loading" class="mem-hint">
        <Icon name="loader" :size="16" class="spin" /> 加载中…
      </div>
      <EmptyState v-else-if="!memories.length" />
      <ul v-else class="mem-list">
        <li v-for="m in memories" :key="m.id" class="mem-item">
          <div class="mem-item-main">
            <span class="mem-type" :class="`tt-${typeTone(m.type)}`">{{ typeLabel(m.type) }}</span>
            <p class="mem-content">{{ m.content }}</p>
            <span class="mem-time">{{ fmtTime(m.createdAt) }}</span>
          </div>
          <button class="action-btn danger" title="删除该条记忆" @click="deleteTarget = m">
            <Icon name="trash" :size="15" />
          </button>
        </li>
      </ul>
    </div>

    <ConfirmDialog
      :show="!!deleteTarget"
      title="删除记忆"
      :message="deleteTarget ? `确认删除这条记忆？\n「${deleteTarget.content}」` : ''"
      confirm-text="删除"
      danger
      :loading="deletingMem"
      @close="deleteTarget = null"
      @confirm="confirmDelete"
    />
    <ConfirmDialog
      :show="showClearConfirm"
      title="清空全部记忆"
      :message="`确认清空全部 ${memories.length} 条长期记忆？此操作不可恢复。`"
      confirm-text="清空"
      danger
      :loading="clearing"
      @close="showClearConfirm = false"
      @confirm="confirmClear"
    />
  </div>
</template>

<style scoped>
.mem-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  margin-bottom: 16px;
}
.mem-head-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.mem-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.mem-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.mem-sub { margin: 0; font-size: 13px; color: var(--text-tertiary); line-height: 1.6; }
.mem-body { padding: 0; overflow: hidden; }
.mem-hint, .mem-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 12px;
  color: var(--text-tertiary);
  font-size: 13px;
}
.mem-list { list-style: none; margin: 0; padding: 0; }
.mem-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  transition: background var(--dur-fast) var(--ease-out);
}
.mem-item:last-child { border-bottom: none; }
.mem-item:hover { background: var(--bg-hover); }
.mem-item-main { flex: 1; min-width: 0; }
.mem-type {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  margin-bottom: 6px;
}
.tt-brand { color: var(--brand); background: var(--brand-soft); }
.tt-violet { color: var(--accent-violet); background: var(--accent-violet-soft); }
.tt-green { color: var(--accent-green); background: var(--accent-green-soft); }
.tt-amber { color: var(--accent-amber); background: var(--accent-amber-soft); }
.mem-content {
  margin: 0 0 6px;
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.mem-time { font-size: 12px; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }

.icon-btn { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: var(--radius-md); color: var(--text-secondary); cursor: pointer; transition: background var(--dur-fast), color var(--dur-fast); }
.icon-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.icon-btn:disabled { opacity: 0.5; cursor: default; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
