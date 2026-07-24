<script setup lang="ts">
// 文档管理 — 按 640(3).png 截图 1:1 还原，接真实文档生命周期。
// scope 由路由决定（mine/public/department/archive）。
import { ref, reactive, computed, onMounted, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import AppModal from '@/components/ui/AppModal.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import Pagination from '@/components/ui/Pagination.vue'
import DataTable from '@/components/ui/DataTable.vue'
import DepartmentTree from '@/components/DepartmentTree.vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'
import {
  getDocuments,
  uploadDocument,
  approveDocument,
  rejectDocument,
  deleteDocument,
  aiReviewDocument,
  getDocument,
  getDepartments,
  getDocumentTags,
  getDocumentTask,
  getDocumentTasks,
  getKbMembers,
  setKbMembers,
} from '@/api'
import { getUserList } from '@/api/auth'
import { uploadToOss } from '@/utils/oss'
import type {
  DocumentItem,
  DocumentDetail,
  AIReview,
  DepartmentNode,
  DocumentTaskOut,
  KBMember,
  UserOut,
} from '@/types/api'

const knowledge = useKnowledgeStore()
const toast = useToastStore()
const auth = useAuthStore()

// KB 选择器选项（严格隔离后，knowledge.bases 仅含当前用户可见的库）
const kbOptions = computed(() =>
  knowledge.bases.map((b) => ({ label: b.name, value: b.id })),
)
const selectedKbName = computed(
  () => knowledge.bases.find((b) => b.id === selectedKb.value)?.name || '',
)

/* ---------- KB 成员管理（库级授权 / 严格隔离下的共享入口）---------- */
const showMemberModal = ref(false)
const memberKbId = ref('')
const memberRows = ref<KBMember[]>([])
const allUsers = ref<UserOut[]>([])
const memberLoading = ref(false)
const memberSaving = ref(false)
const newUserId = ref<string>('')
const newUserLevel = ref<'view' | 'edit' | 'admin'>('view')

const levelOptions = [
  { label: '可查看', value: 'view' },
  { label: '可编辑', value: 'edit' },
  { label: '管理员', value: 'admin' },
]

const availableUserOptions = computed(() => {
  const used = new Set(memberRows.value.map((m) => m.userId))
  return allUsers.value
    .filter((u) => !used.has(u.id))
    .map((u) => ({ label: `${u.displayName || u.username}（@${u.username}）`, value: u.id }))
})

async function openManageMembers() {
  if (!selectedKb.value) {
    toast.warning('请先选择知识库')
    return
  }
  memberKbId.value = selectedKb.value
  showMemberModal.value = true
  memberLoading.value = true
  newUserId.value = ''
  newUserLevel.value = 'view'
  try {
    const [members, users] = await Promise.all([
      getKbMembers(memberKbId.value),
      getUserList(1, 200),
    ])
    memberRows.value = members
    allUsers.value = users.items
  } catch (e: any) {
    toast.error(`加载成员失败：${e?.message || e}`)
    showMemberModal.value = false
  } finally {
    memberLoading.value = false
  }
}

function addMember() {
  const u = allUsers.value.find((x) => x.id === newUserId.value)
  if (!u) return
  if (memberRows.value.some((m) => m.userId === u.id)) {
    toast.warning('该用户已在成员列表中')
    return
  }
  memberRows.value.push({
    userId: u.id,
    username: u.username,
    displayName: u.displayName,
    level: newUserLevel.value,
  })
  newUserId.value = ''
  newUserLevel.value = 'view'
}

function removeMember(userId: string) {
  memberRows.value = memberRows.value.filter((m) => m.userId !== userId)
}

async function saveMembers() {
  const admins = memberRows.value.filter((m) => m.level === 'admin')
  if (!admins.length) {
    toast.error('至少保留一名管理员，否则知识库将无法管理')
    return
  }
  memberSaving.value = true
  try {
    const updated = await setKbMembers(memberKbId.value, {
      members: memberRows.value.map((m) => ({ userId: m.userId, level: m.level })),
    })
    memberRows.value = updated
    toast.success('成员权限已保存')
    showMemberModal.value = false
  } catch (e: any) {
    toast.error(`保存失败：${e?.message || e}`)
  } finally {
    memberSaving.value = false
  }
}

const props = defineProps<{ scope?: string }>()
const scope = computed(() => props.scope ?? 'mine')

const selectedKb = ref<string>('')
const docs = ref<DocumentItem[]>([])
const total = ref(0)
const loading = ref(false)
const deleting = ref(false)
const deleteTarget = ref<DocumentItem | null>(null)
const showBatchDelete = ref(false)

const searchQuery = ref('')
const viewMode = ref<'list' | 'grid'>('list')

// 筛选
const filterType = ref<string>('')
const filterStatus = ref<string>('')
const filterScope = ref<string>('')
const typeOptions = [
  { label: '全部类型', value: '' },
  { label: 'PDF', value: 'PDF' },
  { label: 'Word', value: 'DOCX' },
  { label: 'Excel', value: 'XLSX' },
  { label: 'PPT', value: 'PPTX' },
  { label: 'Markdown', value: 'MD' },
  { label: '图片', value: 'IMAGE' },
  { label: '音频', value: 'AUDIO' },
  { label: '视频', value: 'VIDEO' },
]
const statusOptions = [
  { label: '全部状态', value: '' },
  { label: '解析完成', value: '已审核' },
  { label: '解析中', value: '待复核' },
  { label: '解析失败', value: '已拒绝' },
]
const scopeOptions = [
  { label: '全部权限', value: '' },
  { label: '仅本人可见', value: 'private' },
  { label: '部门可见', value: 'department' },
  { label: '公司可见', value: 'company' },
  { label: '公开可见', value: 'public' },
]

// P5：部门筛选（部门树）+ 标签筛选
const departments = ref<DepartmentNode[]>([])
const filterDept = ref<string>('')
const deptPopoverOpen = ref(false)
const tagOptions = ref<{ label: string; value: string }[]>([])
const filterTag = ref<string>('')

// 当前选中部门名（用于筛选按钮文案）
const deptLabel = computed(() => {
  if (!filterDept.value) return '部门'
  const find = (nodes: DepartmentNode[]): string => {
    for (const n of nodes) {
      if (n.id === filterDept.value) return n.name
      if (n.children?.length) {
        const r = find(n.children)
        if (r) return r
      }
    }
    return ''
  }
  return find(departments.value) || '部门'
})
function onDeptSelect(id: string | null) {
  filterDept.value = id || ''
  deptPopoverOpen.value = false
}

// P5：上传进度（轮询 DocumentTask）
interface UploadTask {
  id: string
  filename: string
  progress: number
  status: 'uploading' | 'processing' | 'done' | 'error'
  message?: string
}
const uploadTasks = ref<UploadTask[]>([])

// 选择（批量删）
const selectedIds = ref<string[]>([])
// 列表列定义（交给通用 DataTable 渲染）
const docColumns = [
  { key: 'name', title: '文档名称', strong: true },
  { key: 'type', title: '文件类型' },
  { key: 'updatedAt', title: '上传时间', mono: true },
  { key: 'uploaderName', title: '上传人' },
  { key: 'parseStatus', title: '文档解析状态' },
  { key: 'scope', title: '权限范围' },
  { key: 'actions', title: '操作' },
]
// 分页
const currentPage = ref(1)
const pageSize = ref(10)

// 弹窗
const previewDoc = ref<DocumentDetail | null>(null)
const previewLoading = ref(false)
const aiReview = ref<AIReview | null>(null)
const aiReviewLoading = ref(false)

// 路由分区（我的/公共/部门/归档）→ 后端查询参数；下拉 scope 可进一步收窄。
// ponytail: 所有过滤下推后端，前端不再做客户端过滤（旧 scopedDocs 已删）。
function buildQuery(): Record<string, string | number | boolean> {
  const q: Record<string, string | number | boolean> = { page: currentPage.value, size: pageSize.value }
  if (scope.value === 'mine') q.mine = true
  else if (scope.value === 'public') q.scope = 'public'
  else if (scope.value === 'department') q.scope = 'department'
  else if (scope.value === 'archive') q.status = '已拒绝'
  if (filterScope.value) q.scope = filterScope.value
  if (filterType.value) q.type = filterType.value
  if (filterStatus.value) q.status = filterStatus.value
  if (searchQuery.value.trim()) q.q = searchQuery.value.trim()
  if (filterDept.value) q.departmentId = filterDept.value
  if (filterTag.value) q.tags = filterTag.value
  return q
}

/* ---------- 数据加载（服务端分页 + 真实过滤）---------- */
async function loadDocs() {
  if (!selectedKb.value) {
    docs.value = []
    total.value = 0
    return
  }
  loading.value = true
  selectedIds.value = []
  try {
    const res = await getDocuments(selectedKb.value, buildQuery() as any)
    docs.value = res.items
    total.value = res.total
  } catch (e: any) {
    docs.value = []
    total.value = 0
    toast.error(`加载文档失败：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!knowledge.loaded) await knowledge.load()
  await loadDepartments()
  if (knowledge.bases.length) {
    selectedKb.value = knowledge.bases[0].id
    await loadTags()
    await loadDocs()
  }
})

watch(selectedKb, async () => {
  currentPage.value = 1
  selectedIds.value = []
  filterDept.value = ''
  filterTag.value = ''
  await loadTags()
  await loadDocs()
})

watch(scope, async () => {
  currentPage.value = 1
  await loadDocs()
})

watch([filterType, filterStatus, filterScope], async () => {
  currentPage.value = 1
  await loadDocs()
})

// P5：部门 / 标签筛选变化 → 重新拉取（服务端真实过滤）
watch([filterDept, filterTag], async () => {
  currentPage.value = 1
  await loadDocs()
})

watch(deptPopoverOpen, (open) => {
  if (open) document.addEventListener('click', onDocClickOutside)
  else document.removeEventListener('click', onDocClickOutside)
})
function onDocClickOutside(e: MouseEvent) {
  const el = document.getElementById('dept-filter-wrap')
  if (el && !el.contains(e.target as Node)) deptPopoverOpen.value = false
}

/* ---------- P5：部门 / 标签 数据 ---------- */
async function loadDepartments() {
  try {
    departments.value = await getDepartments()
  } catch (e: any) {
    departments.value = []
  }
}
async function loadTags() {
  if (!selectedKb.value) {
    tagOptions.value = []
    return
  }
  try {
    const tags = await getDocumentTags(selectedKb.value)
    tagOptions.value = [{ label: '全部标签', value: '' }, ...tags.map((t) => ({ label: t, value: t }))]
  } catch (e: any) {
    tagOptions.value = [{ label: '全部标签', value: '' }]
  }
}

// 搜索防抖后重新拉取（服务端 q 过滤）
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(searchQuery, () => {
  currentPage.value = 1
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { void loadDocs() }, 300)
})

/* ---------- 分页（服务端已分页，仅算总页数）---------- */
const totalPages = computed(() =>
  Math.max(1, Math.ceil(total.value / pageSize.value)),
)

watch([total, pageSize], () => {
  if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
})

function clearSearch() {
  searchQuery.value = ''
}

/* ---------- 工具 ---------- */
function statusType(s: string): 'success' | 'warning' | 'danger' {
  if (s === '已审核') return 'success'
  if (s === '待复核' || s === '解析中') return 'warning'
  return 'danger'
}

// P0：真实解析状态映射（后端 parseStatus 字段，替代原 status 李代桃僵）
function parseStatusType(s: string | undefined): 'success' | 'warning' | 'danger' {
  if (s === 'done') return 'success'
  if (s === 'failed') return 'danger'
  return 'warning' // pending | parsing
}
function parseStatusLabel(s: string | undefined): string {
  if (s === 'done') return '解析完成'
  if (s === 'parsing') return '解析中'
  if (s === 'failed') return '解析失败'
  return '待解析' // pending
}

// P0：真实权限范围映射
function scopeLabel(s: string | undefined): string {
  if (s === 'private') return '仅本人可见'
  if (s === 'department') return '部门可见'
  if (s === 'company') return '公司可见'
  return '公开可见' // public | 默认
}

function fileMeta(type: string): { icon: string; color: string } {
  const t = (type || '').toUpperCase()
  if (t.includes('PDF')) return { icon: 'pdf', color: '#EF4444' }
  if (t.includes('DOC')) return { icon: 'doc', color: '#3B82F6' }
  if (t.includes('XLS')) return { icon: 'excel', color: '#22C55E' }
  if (t.includes('PPT')) return { icon: 'pptx', color: '#F59E0B' }
  if (t.includes('MD') || t.includes('TXT')) return { icon: 'file', color: '#64748B' }
  return { icon: 'file', color: '#94A3B8' }
}

function fmtTime(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function readFileB64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => {
      const res = r.result as string
      const comma = res.indexOf(',')
      resolve(comma >= 0 ? res.slice(comma + 1) : res)
    }
    r.onerror = () => reject(r.error)
    r.readAsDataURL(file)
  })
}

/* ---------- 上传 + 进度条（P5）---------- */
async function onUploadFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length) return
  if (!selectedKb.value) {
    toast.warning('请先在上方选择知识库')
    input.value = ''
    return
  }
  for (const f of files) {
    const entry = reactive<UploadTask>({ id: '', filename: f.name, progress: 0, status: 'uploading' })
    uploadTasks.value.push(entry)
    try {
      // 优先 OSS 前端直传（后端启用时）；未启用或签名被拒则回退旧 base64 流程
      let doc: DocumentItem
      try {
        const { url } = await uploadToOss(f, `uploads/docs/${selectedKb.value}`)
        doc = await uploadDocument(selectedKb.value, f.name, { fileUrl: url })
      } catch (ossErr: any) {
        const msg = String(ossErr?.message || '')
        if (msg.includes('OSS 未启用')) {
          const b64 = await readFileB64(f)
          doc = await uploadDocument(selectedKb.value, f.name, { contentB64: b64 })
        } else {
          throw ossErr
        }
      }
      // 拿到 task id（上传阶段后端已置 done/100，审核阶段会再推进）
      const tasks = await getDocumentTasks(doc.id)
      const task = tasks.items[0]
      if (task) {
        entry.id = task.id
        await pollTask(entry, task.id)
      } else {
        tweenTo(entry, 100, 500)
        entry.status = 'done'
        scheduleRemove(entry)
      }
    } catch (err: any) {
      entry.status = 'error'
      entry.message = err?.message || String(err)
      toast.error(`上传失败：${f.name} - ${err?.message || err}`)
      scheduleRemove(entry)
    }
  }
  input.value = ''
}

// 轮询单个文档任务的真实进度，平滑补间到目标值
async function pollTask(entry: UploadTask, taskId: string) {
  const tick = async () => {
    let t: DocumentTaskOut
    try {
      t = await getDocumentTask(taskId)
    } catch {
      return
    }
    entry.status = t.status === 'failed' ? 'error' : (t.status === 'done' || t.status === 'completed' ? 'done' : 'processing')
    if (t.errorMessage) entry.message = t.errorMessage
    tweenTo(entry, t.progress, 500)
    if (t.status === 'done' || t.status === 'completed' || t.status === 'failed') {
      if (t.status !== 'failed') entry.progress = 100
      scheduleRemove(entry)
      await loadDocs()
      return
    }
    setTimeout(tick, 700)
  }
  await tick()
}

// requestAnimationFrame 平滑补间进度（让 0→100 可见，底层值来自真实 task）
function tweenTo(entry: UploadTask, target: number, ms = 600) {
  const from = entry.progress
  const start = performance.now()
  function frame(now: number) {
    const k = Math.min(1, (now - start) / ms)
    entry.progress = Math.round(from + (target - from) * k)
    if (k < 1) requestAnimationFrame(frame)
    else entry.progress = target
  }
  requestAnimationFrame(frame)
}

function scheduleRemove(entry: UploadTask) {
  setTimeout(() => {
    uploadTasks.value = uploadTasks.value.filter((x) => x !== entry)
  }, 1400)
}

/* ---------- 审核 / 删除 ---------- */
async function onApprove(doc: DocumentItem) {
  if (!selectedKb.value) return
  try {
    await approveDocument(selectedKb.value, doc.id)
    toast.success(`已通过审核：${doc.title}`)
    await loadDocs()
  } catch (e: any) {
    toast.error(`操作失败：${e?.message || e}`)
  }
}

async function onReject(doc: DocumentItem) {
  if (!selectedKb.value) return
  try {
    await rejectDocument(selectedKb.value, doc.id)
    toast.success(`已驳回：${doc.title}`)
    await loadDocs()
  } catch (e: any) {
    toast.error(`操作失败：${e?.message || e}`)
  }
}

function onDelete(doc: DocumentItem) {
  if (!selectedKb.value) return
  deleteTarget.value = doc
}
async function confirmDelete() {
  const doc = deleteTarget.value
  deleteTarget.value = null
  if (!doc || !selectedKb.value) return
  deleting.value = true
  try {
    await deleteDocument(selectedKb.value, doc.id)
    toast.success(`已删除：${doc.title}`)
    await loadDocs()
  } catch (e: any) {
    toast.error(`删除失败：${e?.message || e}`)
  } finally {
    deleting.value = false
  }
}

/* ---------- 预览 ---------- */
async function onPreview(doc: DocumentItem) {
  if (!selectedKb.value) return
  previewLoading.value = true
  previewDoc.value = null
  aiReview.value = null
  try {
    previewDoc.value = await getDocument(selectedKb.value, doc.id)
  } catch (e: any) {
    toast.error(`预览失败：${e?.message || e}`)
  } finally {
    previewLoading.value = false
  }
}

/* ---------- AI 审核（在预览弹窗右侧展示） ---------- */
async function onAiReview(doc: { id: string }) {
  if (!selectedKb.value) return
  aiReviewLoading.value = true
  aiReview.value = null
  try {
    aiReview.value = await aiReviewDocument(selectedKb.value, doc.id)
  } catch (e: any) {
    toast.error(`AI 审核失败：${e?.message || e}`)
  } finally {
    aiReviewLoading.value = false
  }
}

/* ---------- 批量选择 / 删除 ---------- */
function toggleSelect(id: string | number) {
  const sid = String(id)
  const i = selectedIds.value.indexOf(sid)
  if (i >= 0) selectedIds.value.splice(i, 1)
  else selectedIds.value.push(sid)
}
function isSelected(id: string) {
  return selectedIds.value.includes(id)
}
function toggleSelectAllOnPage(checked?: boolean) {
  const pageIds = docs.value.map((d) => d.id)
  const allSelected = checked ?? pageIds.every((id) => selectedIds.value.includes(id))
  if (allSelected) {
    selectedIds.value = selectedIds.value.filter((id) => !pageIds.includes(id))
  } else {
    const set = new Set(selectedIds.value)
    pageIds.forEach((id) => set.add(id))
    selectedIds.value = Array.from(set)
  }
}
function clearSelection() {
  selectedIds.value = []
}

function onBatchDelete() {
  if (!selectedIds.value.length || !selectedKb.value) return
  showBatchDelete.value = true
}
async function confirmBatchDelete() {
  const n = selectedIds.value.length
  showBatchDelete.value = false
  deleting.value = true
  let ok = 0
  for (const id of [...selectedIds.value]) {
    try {
      await deleteDocument(selectedKb.value, id)
      ok++
    } catch (e: any) {
      toast.error(`删除失败：${e?.message || e}`)
    }
  }
  deleting.value = false
  selectedIds.value = []
  toast.success(`已删除 ${ok}/${n} 篇文档`)
  await loadDocs()
}

</script>

<template>
  <div class="docs-page">
    <!-- 分区说明横幅 -->
    <div v-if="scope === 'archive'" class="scope-banner warn">
      <Icon name="archive" :size="14" />
      <span>文档归档：仅展示状态为「已拒绝」的文档。</span>
    </div>

    <!-- ====== 工具栏 ====== -->
    <div class="toolbar card">
      <div class="toolbar-left">
        <!-- KB 选择器（严格隔离后仅列当前用户可见的库） -->
        <CustomSelect
          v-model="selectedKb"
          :options="kbOptions"
          placeholder="选择知识库"
          width="180px"
        />
        <button
          v-if="auth.isAdmin && selectedKb"
          class="btn btn-ghost btn-sm"
          :disabled="memberLoading"
          title="管理该知识库可访问的成员"
          @click="openManageMembers"
        >
          <Icon name="users" :size="13" /> 管理成员
        </button>

        <!-- 搜索 -->
        <div class="search-box">
          <Icon name="search" :size="14" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索文档名称、内容、上传人等" class="search-input" />
          <button v-if="searchQuery" class="search-clear" @click="clearSearch">
            <Icon name="close" :size="12" />
          </button>
        </div>

        <!-- 批量上传 -->
        <label class="btn btn-primary btn-sm upload-btn" :class="{ 'is-loading': uploadTasks.length > 0 }">
          <Icon name="upload" :size="13" /> {{ uploadTasks.length > 0 ? '上传中…' : '批量上传' }}
          <input type="file" multiple accept=".md,.txt,.docx,.pdf,.png,.jpg,.jpeg,.gif,.bmp,.webp,.mp3,.wav,.m4a,.ogg,.flac,.mp4,.mov,.webm,.mkv,.avi" class="file-hidden" @change="onUploadFiles" />
        </label>

        <!-- 筛选下拉组 -->
        <CustomSelect v-model="filterType" :options="typeOptions" placeholder="文件类型" width="110px" />
        <CustomSelect v-model="filterStatus" :options="statusOptions" placeholder="解析状态" width="110px" />
        <CustomSelect v-model="filterScope" :options="scopeOptions" placeholder="权限范围" width="110px" />

        <!-- P5：部门筛选（弹出部门树） -->
        <div id="dept-filter-wrap" class="dept-filter-wrap">
          <button class="btn-filter" :class="{ active: !!filterDept }" @click.stop="deptPopoverOpen = !deptPopoverOpen">
            <Icon name="users" :size="13" />
            <span>{{ deptLabel }}</span>
            <Icon name="chevron-down" :size="11" />
          </button>
          <div v-if="deptPopoverOpen" class="dept-popover card">
            <DepartmentTree :nodes="departments" :selected-id="filterDept" @select="onDeptSelect" />
          </div>
        </div>

        <!-- P5：标签筛选 -->
        <CustomSelect v-model="filterTag" :options="tagOptions" placeholder="标签" width="120px" />

        <!-- 刷新 -->
        <button class="icon-btn" title="刷新" :disabled="loading" @click="loadDocs">
          <Icon name="refresh" :size="15" :class="{ spin: loading }" />
        </button>
      </div>

      <div class="toolbar-right">
        <button class="view-toggle" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'">
          <Icon name="listview" :size="16" />
        </button>
        <button class="view-toggle" :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'">
          <Icon name="gridview" :size="16" />
        </button>
      </div>
    </div>

    <!-- ====== 批量操作条 ====== -->
    <Transition name="slide-down">
      <div v-if="selectedIds.length" class="batch-bar card">
        <span class="batch-count">已选 <b>{{ selectedIds.length }}</b> 篇</span>
        <button class="btn btn-danger btn-sm" :disabled="deleting" @click="onBatchDelete">
          <Icon name="trash" :size="13" /> 批量删除
        </button>
        <button class="btn btn-ghost btn-sm" @click="clearSelection">取消选择</button>
      </div>
    </Transition>

    <!-- ====== 上传进度条（P5 轮询 DocumentTask）====== -->
    <Transition name="slide-down">
      <div v-if="uploadTasks.length" class="upload-progress card">
        <div v-for="t in uploadTasks" :key="(t.id || t.filename)" class="up-item">
          <Icon
            :name="t.status === 'error' ? 'alert' : (t.status === 'done' ? 'check' : 'loader')"
            :size="14"
            :class="{ spin: t.status === 'uploading' || t.status === 'processing' }"
            :style="t.status === 'error' ? 'color:var(--danger)' : (t.status === 'done' ? 'color:var(--success)' : '')"
          />
          <span class="up-name" :title="t.filename">{{ t.filename }}</span>
          <div class="up-bar">
            <div class="up-fill" :class="t.status" :style="{ width: t.progress + '%' }"></div>
          </div>
          <span class="up-pct">{{ t.status === 'error' ? '失败' : t.progress + '%' }}</span>
        </div>
      </div>
    </Transition>

    <!-- ====== 列表 / 网格 ====== -->
    <div class="card" v-if="viewMode === 'list'">
      <DataTable
        :columns="docColumns"
        :rows="docs"
        row-key="id"
        selectable
        :selected-keys="selectedIds"
        :loading="loading"
        @toggle-row="toggleSelect"
        @toggle-all="toggleSelectAllOnPage"
      >
        <template #cell="{ row, col }">
          <template v-if="col.key === 'name'">
            <div class="file-name-cell">
              <span class="file-icon-sm" :style="{ background: fileMeta(row.type).color + '18', color: fileMeta(row.type).color }">
                <Icon :name="fileMeta(row.type).icon" :size="15" />
              </span>
              <span class="file-name" :title="row.title">{{ row.title }}</span>
            </div>
          </template>
          <template v-else-if="col.key === 'type'">
            <span class="type-text">{{ row.type }}</span>
          </template>
          <template v-else-if="col.key === 'updatedAt'">
            {{ fmtTime(row.updatedAt) }}
          </template>
          <template v-else-if="col.key === 'uploaderName'">
            {{ row.uploaderName || '—' }}
          </template>
          <template v-else-if="col.key === 'parseStatus'">
            <span class="status-tag" :class="parseStatusType(row.parseStatus)">{{ parseStatusLabel(row.parseStatus) }}</span>
          </template>
          <template v-else-if="col.key === 'scope'">
            <span class="scope-tag" :class="{ 'scope-private': row.scope === 'private' }">{{ scopeLabel(row.scope) }}</span>
          </template>
          <template v-else-if="col.key === 'actions'">
            <div class="row-actions">
              <button class="action-btn" title="预览" @click="onPreview(row)"><Icon name="eye" :size="15" /></button>
              <button class="action-btn" title="通过审核" @click="onApprove(row)"><Icon name="check" :size="15" /></button>
              <button class="action-btn" title="驳回" @click="onReject(row)"><Icon name="close" :size="15" /></button>
              <button class="action-btn" title="删除" @click="onDelete(row)"><Icon name="trash" :size="15" /></button>
            </div>
          </template>
        </template>
        <template #empty>
          {{ selectedKb ? '该知识库暂无文档，点击「上传文档」添加' : '请选择左侧知识库' }}
        </template>
      </DataTable>
    </div>

    <!-- 网格视图 -->
    <div class="file-grid" v-else>
      <div
        v-for="d in docs"
        :key="d.id"
        class="doc-card"
        :class="{ 'row-selected': isSelected(d.id) }"
        @click="toggleSelect(d.id)"
      >
        <div class="doc-card-top">
          <span class="file-icon-sm" :style="{ background: fileMeta(d.type).color + '18', color: fileMeta(d.type).color }">
            <Icon :name="fileMeta(d.type).icon" :size="18" />
          </span>
          <span class="status-badge mini" :class="statusType(d.status)">{{ d.status }}</span>
        </div>
        <div class="doc-card-title" :title="d.title">{{ d.title }}</div>
        <div class="doc-card-meta">{{ d.type }} · {{ fmtTime(d.updatedAt) }}</div>
        <div class="doc-card-actions" @click.stop>
          <button class="action-btn" title="预览" @click="onPreview(d)"><Icon name="eye" :size="15" /></button>
          <button class="action-btn" title="通过审核" @click="onApprove(d)"><Icon name="check" :size="15" /></button>
          <button class="action-btn" title="驳回" @click="onReject(d)"><Icon name="close" :size="15" /></button>
          <button class="action-btn" title="删除" @click="onDelete(d)"><Icon name="trash" :size="15" /></button>
        </div>
      </div>
      <div v-if="!loading && !docs.length" class="grid-empty">
        {{ selectedKb ? '该知识库暂无文档' : '请选择左侧知识库' }}
      </div>
    </div>

    <!-- ====== 分页 ====== -->
    <Pagination
      v-if="total > 0"
      v-model:page="currentPage"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50]"
      @update:page="loadDocs()"
      @update:page-size="currentPage = 1; loadDocs()"
    />

    <!-- ====== 预览弹窗（含 AI 辅助审核） ====== -->
    <AppModal :show="!!previewDoc" title="文档预览" wide @close="previewDoc = null">
      <div v-if="previewLoading" class="modal-hint">加载中…</div>
      <template v-else-if="previewDoc">
        <div class="preview-toolbar">
          <button
            class="btn btn-primary btn-sm"
            :disabled="aiReviewLoading"
            @click="onAiReview(previewDoc)"
          >
            <span v-if="aiReviewLoading" class="spinner sm"></span>
            {{ aiReviewLoading ? '分析中…' : (aiReview ? '重新审核' : 'AI 审核') }}
          </button>
        </div>
        <div class="preview-split">
          <!-- 左：文档内容 -->
          <div class="preview-left">
            <div class="preview-meta">
              <span class="type-text">{{ previewDoc.type }}</span>
              <span class="col-time">{{ fmtTime(previewDoc.updatedAt) }}</span>
              <span class="status-badge mini" :class="statusType(previewDoc.status)">{{ previewDoc.status }}</span>
            </div>
            <pre class="preview-body">{{ previewDoc.contentMd || '（无内容）' }}</pre>
          </div>
          <!-- 右：AI 审核建议 -->
          <aside class="preview-right">
            <div class="ai-panel-head">AI 辅助审核</div>
            <div v-if="aiReviewLoading" class="ai-loading">
              <span class="spinner"></span>
              正在调用大模型分析文档，请稍候…
            </div>
            <template v-else-if="aiReview">
              <div class="ai-verdict" :class="aiReview.verdict">
                建议：{{ aiReview.verdict === 'approve' ? '通过' : aiReview.verdict === 'reject' ? '驳回' : '人工复核' }}
              </div>
              <p class="ai-summary">{{ aiReview.summary }}</p>
              <div v-if="aiReview.similarityFindings?.length" class="ai-section">
                <h4>相似文档</h4>
                <ul class="ai-list">
                  <li v-for="(f, i) in aiReview.similarityFindings" :key="i">
                    <span class="ai-sim">相似度 {{ (f.similarity * 100).toFixed(0) }}%</span>
                    <span class="ai-doc">{{ f.docTitle }}</span>
                    <p class="ai-snippet">{{ f.snippet }}</p>
                  </li>
                </ul>
              </div>
              <div v-if="aiReview.qualityNotes?.length" class="ai-section">
                <h4>质量建议</h4>
                <ul class="ai-list"><li v-for="(q, i) in aiReview.qualityNotes" :key="i">{{ q }}</li></ul>
              </div>
              <div v-if="aiReview.outdatedFindings?.length" class="ai-section">
                <h4>过时内容</h4>
                <ul class="ai-list"><li v-for="(o, i) in aiReview.outdatedFindings" :key="i">{{ o }}</li></ul>
              </div>
            </template>
            <div v-else class="ai-empty">
              点击左上角「AI 审核」按钮，调用大模型分析该文档并给出建议。
            </div>
          </aside>
        </div>
      </template>
    </AppModal>

    <ConfirmDialog
      :show="!!deleteTarget"
      title="删除文档"
      :message="deleteTarget ? `确认删除文档「${deleteTarget.title}」？该操作会级联清理向量与图谱数据。` : ''"
      confirm-text="删除"
      danger
      @close="deleteTarget = null"
      @confirm="confirmDelete"
    />
    <ConfirmDialog
      :show="showBatchDelete"
      title="批量删除文档"
      :message="`确认批量删除选中的 ${selectedIds.length} 篇文档？该操作不可恢复。`"
      confirm-text="批量删除"
      danger
      @close="showBatchDelete = false"
      @confirm="confirmBatchDelete"
    />

    <!-- ====== KB 成员管理（库级授权）====== -->
    <AppModal
      :show="showMemberModal"
      :title="`管理成员 · ${selectedKbName}`"
      wide
      @close="showMemberModal = false"
    >
      <div v-if="memberLoading" class="modal-hint">加载中…</div>
      <template v-else>
        <p class="member-tip">
          为该知识库添加成员并分配权限：<b>可查看</b>仅检索、<b>可编辑</b>可上传/删除文档、<b>管理员</b>可管理成员与库设置。至少保留一名管理员。
        </p>
        <div class="member-list">
          <div v-for="m in memberRows" :key="m.userId" class="member-row">
            <div class="member-info">
              <span class="member-name">{{ m.displayName || m.username }}</span>
              <span class="member-uname">@{{ m.username }}</span>
            </div>
            <CustomSelect v-model="m.level" :options="levelOptions" width="110px" />
            <button class="action-btn" title="移除成员" @click="removeMember(m.userId)">
              <Icon name="close" :size="15" />
            </button>
          </div>
          <div v-if="!memberRows.length" class="member-empty">暂无成员，请在下方添加。</div>
        </div>
        <div class="member-add">
          <CustomSelect v-model="newUserId" :options="availableUserOptions" placeholder="选择用户" width="220px" />
          <CustomSelect v-model="newUserLevel" :options="levelOptions" width="110px" />
          <button class="btn btn-primary btn-sm" :disabled="!newUserId" @click="addMember">添加</button>
        </div>
      </template>
      <template #foot>
        <button class="btn btn-ghost btn-sm" @click="showMemberModal = false">取消</button>
        <button class="btn btn-primary btn-sm" :disabled="memberSaving" @click="saveMembers">
          <span v-if="memberSaving" class="spinner sm"></span> 保存
        </button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.docs-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
/* 分区说明横幅 */
.scope-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: var(--brand-soft);
  color: var(--text-secondary);
  font-size: 12.5px;
  line-height: 1.5;
}
.scope-banner :deep(svg) { color: var(--brand); flex-shrink: 0; }
.scope-banner.warn { background: var(--warning-soft); }
.scope-banner.warn :deep(svg) { color: var(--warning); }

/* ---- 工具栏 ---- */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  gap: 12px;
  flex-wrap: wrap;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

/* 搜索框 */
.search-box {
  position: relative;
  width: 240px;
}
.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-tertiary);
  pointer-events: none;
}
.search-input {
  width: 100%;
  height: 34px;
  padding: 0 30px 0 32px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
  background: var(--bg-surface);
  transition: all var(--dur-fast);
}
.search-input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.search-clear {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  color: var(--text-tertiary);
  cursor: pointer;
  background: transparent;
}
.search-clear:hover { background: var(--bg-hover); }

/* 上传按钮（label 包裹 input） */
.upload-btn { position: relative; overflow: hidden; cursor: pointer; }
.file-hidden {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
  width: 100%;
}
.upload-btn.is-loading { opacity: 0.7; pointer-events: none; }

.view-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 33px;
  height: 33px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--dur-fast);
}
.view-toggle:hover { background: var(--bg-hover); color: var(--text-secondary); }
.view-toggle.active { background: var(--brand); color: var(--text-on-brand); border-color: var(--brand); }
.icon-btn:disabled { opacity: 0.5; cursor: default; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 批量条 */
.batch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-left: 3px solid var(--brand);
}
.batch-count { font-size: 13px; color: var(--text-secondary); }
.batch-count b { color: var(--text-primary); }
.btn-danger { background: var(--danger); color: var(--text-on-brand); border-color: var(--danger); }
.btn-danger:hover { background: var(--danger-hover); }
.btn-danger:disabled { opacity: 0.6; }
.slide-down-enter-active, .slide-down-leave-active { transition: all 0.2s var(--ease-out); }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; transform: translateY(-6px); }

/* ---- P5：部门筛选 + 弹出树 ---- */
.dept-filter-wrap { position: relative; }
.btn-filter {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--dur-fast);
}
.btn-filter:hover { border-color: var(--brand); color: var(--text-primary); }
.btn-filter.active { border-color: var(--brand); color: var(--brand); background: var(--brand-soft); }
.dept-popover {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 30;
  min-width: 240px;
  max-height: 360px;
  overflow: auto;
  padding: 4px;
  box-shadow: var(--shadow-pop);
}

/* ---- P5：上传进度条 ---- */
.upload-progress {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 16px;
}
.up-item { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.up-name {
  flex: 0 0 180px;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
}
.up-bar {
  flex: 1;
  height: 7px;
  border-radius: 99px;
  background: var(--bg-subtle);
  overflow: hidden;
}
.up-fill {
  height: 100%;
  border-radius: 99px;
  background: var(--brand);
  transition: width 0.25s var(--ease-out);
}
.up-fill.done { background: var(--success); }
.up-fill.error { background: var(--danger); }
.up-pct { flex: 0 0 44px; text-align: right; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }


.file-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 360px;
}
.file-icon-sm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  flex-shrink: 0;
}
.file-name {
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.type-text { color: var(--text-secondary); font-weight: 500; }
.col-time { color: var(--text-tertiary); white-space: nowrap; }

/* 状态标签（原型风格） */
.status-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 11px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 500;
}
.status-tag.success { background: var(--success-soft); color: var(--success); }
.status-tag.warning { background: var(--warning-soft); color: var(--warning); }
.status-tag.danger { background: var(--danger-soft); color: var(--danger); }

/* 权限范围标签 */
.scope-tag {
  display: inline-flex;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  background: var(--accent-blue-soft);
  color: var(--accent-blue);
}
.scope-tag.scope-private { background: var(--bg-subtle); color: var(--text-tertiary); }

/* 兼容旧 .status-badge */
.status-badge {
  display: inline-flex; align-items: center; padding: 2px 10px;
  border-radius: var(--radius-pill); font-size: 12px; font-weight: 500;
}
.status-badge.success { background: var(--success-soft); color: var(--success); }
.status-badge.warning { background: var(--warning-soft); color: var(--warning); }
.status-badge.danger { background: var(--danger-soft); color: var(--danger); }
.status-badge.mini { padding: 1px 8px; font-size: 11px; }

.row-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  background: transparent;
  cursor: pointer;
  transition: all var(--dur-fast);
}
.action-btn:hover { background: var(--bg-hover); color: var(--text-primary); }

.empty-cell {
  text-align: center;
  color: var(--text-tertiary);
  padding: 32px 0 !important;
}

/* ---- 网格视图 ---- */
.file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}
.doc-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
  transition: all var(--dur-fast);
}
.doc-card:hover { border-color: var(--brand); box-shadow: var(--shadow-pop); }
.doc-card.row-selected { border-color: var(--brand); background: var(--brand-soft); }
.doc-card-top { display: flex; align-items: center; justify-content: space-between; }
.doc-card-title {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.doc-card-meta { font-size: 12px; color: var(--text-tertiary); }
.doc-card-actions {
  display: flex;
  gap: 2px;
  margin-top: 2px;
}
.grid-empty {
  grid-column: 1 / -1;
  text-align: center;
  color: var(--text-tertiary);
  padding: 40px 0;
}

/* ---- 弹窗内容 ---- */
.modal-hint { color: var(--text-tertiary); text-align: center; padding: 20px 0; }
.ai-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 0;
  color: var(--text-secondary);
  font-size: 14px;
}
.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border);
  border-top-color: var(--brand);
  border-radius: 50%;
  animation: ai-spin 0.7s linear infinite;
}
.spinner.sm {
  width: 13px;
  height: 13px;
  border-width: 2px;
}
@keyframes ai-spin { to { transform: rotate(360deg); } }
.preview-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 12px;
}
.preview-body {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
  line-height: 1.7;
  max-height: 52vh;
  overflow-y: auto;
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  padding: 14px;
  margin: 0;
  color: var(--text-secondary);
}
/* 预览弹窗顶部工具条（AI 审核触发） */
.preview-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}
/* 预览 + AI 审核左右分栏 */
.preview-split {
  display: flex;
  gap: 16px;
  align-items: stretch;
}
.preview-left {
  flex: 1 1 auto;
  min-width: 0;
}
.preview-right {
  flex: 0 0 268px;
  border-left: 1px solid var(--border);
  padding-left: 16px;
  max-height: 58vh;
  overflow-y: auto;
}
.ai-panel-head {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
}
.ai-empty {
  font-size: 13px;
  color: var(--text-tertiary);
  line-height: 1.6;
  padding: 12px 0;
}
.ai-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 24px 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.ai-verdict {
  display: inline-block;
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 10px;
}
.ai-verdict.approve { background: var(--success-soft); color: var(--success); }
.ai-verdict.reject { background: var(--danger-soft); color: var(--danger); }
.ai-verdict.manual_review, .ai-verdict.manual { background: var(--warning-soft); color: var(--warning); }
.ai-summary { margin: 0 0 14px; color: var(--text-secondary); line-height: 1.6; }
.ai-section h4 { font-size: 13px; color: var(--text-primary); margin: 14px 0 6px; }
.ai-list { margin: 0; padding-left: 18px; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.ai-list li { margin-bottom: 8px; }
.ai-sim { color: var(--brand); font-weight: 600; margin-right: 8px; }
.ai-doc { font-weight: 500; color: var(--text-primary); }
.ai-snippet { margin: 4px 0 0; color: var(--text-tertiary); font-size: 12px; }

/* ===== KB 成员管理弹窗 ===== */
.member-tip { margin: 0 0 14px; color: var(--text-tertiary); font-size: 12.5px; line-height: 1.6; }
.member-tip b { color: var(--text-secondary); }
.member-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.member-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.member-info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.member-name { font-size: 13.5px; font-weight: 600; color: var(--text-primary); }
.member-uname { font-size: 12px; color: var(--text-tertiary); }
.member-empty { padding: 14px; text-align: center; color: var(--text-tertiary); font-size: 13px; background: var(--bg-soft); border: 1px dashed var(--border); border-radius: var(--radius-md); }
.member-add { display: flex; align-items: center; gap: 10px; padding-top: 14px; border-top: 1px solid var(--border); }
</style>
