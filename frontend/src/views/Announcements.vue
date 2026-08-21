<script setup lang="ts">
// 首页大盘 — 系统公告（列表 + admin 新建/编辑/删除/置顶）。
import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import RefreshButton from '@/components/ui/RefreshButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useAsyncAction, useKeyedAsyncAction } from '@/composables/useAsyncAction'
import { getAnnouncements, createAnnouncement, updateAnnouncement, deleteAnnouncement } from '@/api'
import '@/assets/dashboard.css'
import type { Announcement, AnnouncementCreate } from '@/types/api'

const auth = useAuthStore()

const announcements = ref<Announcement[]>([])
async function loadAnnouncements(force = false) { announcements.value = (await getAnnouncements(1, 20, force)).items }

const showAnnModal = ref(false)
const editingAnn = ref<Announcement | null>(null)
const { busy: savingAnn, run: runSaveAnn } = useAsyncAction({ errorPrefix: '保存公告失败' })
const deleteTarget = ref<Announcement | null>(null)
const { busy: deletingAnn, run: runDeleteAnn } = useAsyncAction({ errorPrefix: '删除公告失败' })
const annForm = ref({ title: '', content: '', level: 'info' as AnnouncementCreate['level'], pinned: false })
const LEVEL_OPTIONS: { value: NonNullable<AnnouncementCreate['level']>; label: string }[] = [
  { value: 'info', label: '普通' },
  { value: 'warning', label: '警告' },
  { value: 'success', label: '成功' },
  { value: 'error', label: '严重' },
]
function resetAnnForm() {
  annForm.value = { title: '', content: '', level: 'info', pinned: false }
  editingAnn.value = null
}
function openCreateAnn() {
  resetAnnForm()
  showAnnModal.value = true
}
function openEditAnn(a: Announcement) {
  editingAnn.value = a
  annForm.value = { title: a.title, content: a.content, level: a.level, pinned: a.pinned }
  showAnnModal.value = true
}
async function saveAnn() {
  const { title, content, level, pinned } = annForm.value
  if (!title.trim() || !content.trim()) return
  await runSaveAnn(async () => {
    if (editingAnn.value) {
      await updateAnnouncement(editingAnn.value.id, { title, content, level, pinned })
    } else {
      await createAnnouncement({ title, content, level, pinned })
    }
    showAnnModal.value = false
    await loadAnnouncements()
  })
}
// 置顶切换：per-id 在途守卫，防止连点同一条产生重复请求/状态翻转竞态
const { run: runPin, isBusy: isPinning } = useKeyedAsyncAction({ errorPrefix: '置顶操作失败' })
async function togglePin(a: Announcement) {
  await runPin(a.id, async () => {
    await updateAnnouncement(a.id, { pinned: !a.pinned })
    await loadAnnouncements()
  })
}
async function confirmDeleteAnn() {
  if (!deleteTarget.value) return
  const id = deleteTarget.value.id
  await runDeleteAnn(async () => {
    await deleteAnnouncement(id)
    deleteTarget.value = null
    await loadAnnouncements()
  })
}

function fmtTime(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

loadAnnouncements()
</script>

<template>
  <div class="dashboard">
    <div class="ann-panel card">
      <div v-if="auth.hasPerm('doc_edit')" class="ann-toolbar">
        <RefreshButton @click="loadAnnouncements(true)" />
        <button class="btn btn-primary btn-sm" @click="openCreateAnn">
          <Icon name="plus" :size="14" /> 新建公告
        </button>
      </div>
      <div v-if="announcements.length" class="ann-list">
      <div v-for="a in announcements" :key="a.id" class="ann-card card" :class="'lv-' + a.level">
        <div class="ann-head">
          <Icon :name="a.pinned ? 'pin' : 'bell'" :size="15" class="ann-ic" />
          <span class="ann-title">{{ a.title }}</span>
          <span v-if="a.pinned" class="ann-pin">置顶</span>
          <span class="ann-level" :class="'lvl-' + a.level">{{ { info: '普通', warning: '警告', success: '成功', error: '严重' }[a.level] }}</span>
          <span class="ann-time">{{ fmtTime(a.createdAt) }}</span>
          <template v-if="auth.hasPerm('doc_edit')">
            <button class="ann-action" title="编辑" @click="openEditAnn(a)"><Icon name="edit" :size="14" /></button>
            <button class="ann-action" :title="a.pinned ? '取消置顶' : '置顶'" :disabled="isPinning(a.id)" @click="togglePin(a)">
              <Icon :name="a.pinned ? 'pin-off' : 'pin'" :size="14" />
            </button>
            <button class="ann-action danger" title="删除" @click="deleteTarget = a"><Icon name="trash-2" :size="14" /></button>
          </template>
        </div>
        <div class="ann-content">{{ a.content }}</div>
      </div>
    </div>
    <EmptyState v-else />
    </div>

    <AppModal :show="showAnnModal" :title="editingAnn ? '编辑公告' : '新建公告'" wide @close="showAnnModal = false">
      <div class="ann-form">
        <div class="form-row">
          <label class="form-label">标题</label>
          <input v-model="annForm.title" class="form-input" placeholder="公告标题" maxlength="200" />
        </div>
        <div class="form-row">
          <label class="form-label">级别</label>
          <div class="seg">
            <button
              v-for="opt in LEVEL_OPTIONS"
              :key="opt.value"
              class="seg-btn"
              :class="{ active: annForm.level === opt.value }"
              @click="annForm.level = opt.value"
            >{{ opt.label }}</button>
          </div>
        </div>
        <div class="form-row">
          <label class="form-label">置顶</label>
          <label class="switch">
            <input type="checkbox" v-model="annForm.pinned" />
            <span class="switch-track"><span class="switch-knob" /></span>
            <span class="switch-text">{{ annForm.pinned ? '置顶' : '不置顶' }}</span>
          </label>
        </div>
        <div class="form-row align-start">
          <label class="form-label">内容</label>
          <textarea v-model="annForm.content" class="form-input ann-textarea" placeholder="公告内容" rows="6" />
        </div>
      </div>
      <template #foot>
        <button class="btn btn-ghost btn-sm" @click="showAnnModal = false">取消</button>
        <button
          class="btn btn-primary btn-sm"
          :disabled="savingAnn || !annForm.title.trim() || !annForm.content.trim()"
          @click="saveAnn"
        >{{ savingAnn ? '保存中…' : '保存' }}</button>
      </template>
    </AppModal>

    <ConfirmDialog
      :show="!!deleteTarget"
      title="删除公告"
      :message="deleteTarget ? `确认删除公告「${deleteTarget.title}」？该操作不可恢复。` : ''"
      confirm-text="删除"
      danger
      :loading="deletingAnn"
      @close="deleteTarget = null"
      @confirm="confirmDeleteAnn"
    />
  </div>
</template>
