<script setup lang="ts">
// 记忆管理 — 个人中心下的长期记忆（Mem0 轻量版）列表 / 单条删除 / 清空。
// 写记忆发生在每次问答的后台任务里；本页只做「可读 / 可忘」。
import { ref, onMounted } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import { useToastStore } from '@/stores/toast'
import { getMemories, deleteMemory, clearMemories } from '@/api'
import type { MemoryItem } from '@/types/api'

const toast = useToastStore()

const memories = ref<MemoryItem[]>([])
const loading = ref(false)

const deleteTarget = ref<MemoryItem | null>(null)
const showClearConfirm = ref(false)
const clearing = ref(false)

const TYPE_LABEL: Record<string, string> = {
  user_profile: '用户画像',
  preference: '偏好',
  fact: '事实',
  feedback: '反馈',
}
function typeLabel(t: string | null) {
  return (t && TYPE_LABEL[t]) || t || '其他'
}

function fmtTime(s: string | null) {
  if (!s) return '—'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadMemories() {
  loading.value = true
  try {
    memories.value = await getMemories()
  } catch (e: any) {
    memories.value = []
    toast.error(`加载记忆失败：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

async function confirmDelete() {
  const target = deleteTarget.value
  if (!target) return
  try {
    await deleteMemory(target.id)
    memories.value = memories.value.filter((m) => m.id !== target.id)
    toast.success('已删除该条记忆')
  } catch (e: any) {
    toast.error(`删除失败：${e?.message || e}`)
  } finally {
    deleteTarget.value = null
  }
}

async function confirmClear() {
  if (clearing.value) return
  clearing.value = true
  try {
    const n = await clearMemories()
    memories.value = []
    toast.success(`已清空 ${n} 条记忆`)
  } catch (e: any) {
    toast.error(`清空失败：${e?.message || e}`)
  } finally {
    clearing.value = false
    showClearConfirm.value = false
  }
}

onMounted(loadMemories)
</script>

<template>
  <div class="mem-page">
    <div class="mem-head">
      <div>
        <h1 class="mem-title">记忆管理</h1>
        <p class="mem-sub">系统会在问答过程中自动学习关于你的长期记忆（用户画像、偏好、关键事实等），你可以在此查看或遗忘。</p>
      </div>
      <button
        class="btn btn-danger btn-sm"
        :disabled="!memories.length || clearing"
        @click="showClearConfirm = true"
      >
        <Icon name="trash" :size="13" /> 清空全部
      </button>
    </div>

    <div class="card mem-body">
      <div v-if="loading" class="mem-hint">
        <Icon name="loader" :size="16" class="spin" /> 加载中…
      </div>
      <div v-else-if="!memories.length" class="mem-empty">
        <Icon name="book-marked" :size="32" />
        <p>暂无长期记忆。多聊几次，系统会逐渐记住你的偏好。</p>
      </div>
      <ul v-else class="mem-list">
        <li v-for="m in memories" :key="m.id" class="mem-item">
          <div class="mem-item-main">
            <span class="mem-type">{{ typeLabel(m.type) }}</span>
            <p class="mem-content">{{ m.content }}</p>
            <span class="mem-time">{{ fmtTime(m.createdAt) }}</span>
          </div>
          <button class="action-btn" title="删除该条记忆" @click="deleteTarget = m">
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
      @close="deleteTarget = null"
      @confirm="confirmDelete"
    />
    <ConfirmDialog
      :show="showClearConfirm"
      title="清空全部记忆"
      :message="`确认清空全部 ${memories.length} 条长期记忆？此操作不可恢复。`"
      confirm-text="清空"
      danger
      @close="showClearConfirm = false"
      @confirm="confirmClear"
    />
  </div>
</template>

<style scoped>
.mem-page { max-width: 880px; margin: 0 auto; }
.mem-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.mem-title { font-size: 20px; font-weight: 700; color: var(--text-primary); margin: 0 0 6px; }
.mem-sub { margin: 0; font-size: 13px; color: var(--text-tertiary); line-height: 1.6; max-width: 640px; }
.mem-body { padding: 8px 4px; }
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
  padding: 14px 14px;
  border-bottom: 1px solid var(--border);
}
.mem-item:last-child { border-bottom: none; }
.mem-item-main { flex: 1; min-width: 0; }
.mem-type {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  color: var(--brand);
  background: var(--brand-soft);
  padding: 2px 8px;
  border-radius: 999px;
  margin-bottom: 6px;
}
.mem-content {
  margin: 0 0 6px;
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.mem-time { font-size: 12px; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }
</style>
