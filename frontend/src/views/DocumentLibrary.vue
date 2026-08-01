<script setup lang="ts">
// 文档管理 — 按 640(3).png 截图 1:1 还原，接真实文档生命周期。
// scope 由路由决定（mine/public/department/archive）。
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, markRaw } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import DepartmentSelect from '@/components/ui/DepartmentSelect.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import Pagination from '@/components/ui/Pagination.vue'
import DataTable from '@/components/ui/DataTable.vue'
import DepartmentTreeSelect from '@/components/ui/DepartmentTreeSelect.vue'
import DocPreviewModal from '@/components/documents/DocPreviewModal.vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { useAuthStore } from '@/stores/auth'
import { useBackdropClick } from '@/composables/useBackdropClick'
import {
  getDocuments,
  uploadDocument,
  approveDocument,
  rejectDocument,
  deleteDocument,
  batchApproveDocuments,
  getDocument,
  getDepartments,
  getDocumentTask,
  getDocumentTasks,
} from '@/api'
import { uploadToOss } from '@/utils/oss'
import type {
  DocumentItem,
  DocumentDetail,
  DepartmentNode,
  DocumentTaskOut,
} from '@/types/api'

const knowledge = useKnowledgeStore()
const toast = useToastStore()
const auth = useAuthStore()

// KB 选择器选项（严格隔离后，knowledge.bases 仅含当前用户可见的库）
const kbOptions = computed(() =>
  knowledge.bases.map((b) => ({ label: b.name, value: b.id })),
)

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
  { label: '本人可见', value: 'private' },
  { label: '部门可见', value: 'department' },
  { label: '公开可见', value: 'public' },
]
// scope 补全：上传时指定文档权限范围；默认 department（有权限时），否则 public。
// department：部门可见，可手动指定归属部门（不选则后端默认取上传者部门）。
const uploadScope = ref<string>('department')
const uploadDeptId = ref<string>('')
// 非管理员无部门时只能选公开/本人；有部门时可选部门可见（锁定本人部门）
const uploadScopeOptions = computed(() => {
  const opts = [
    { label: '公开可见', value: 'public' },
    { label: '本人可见', value: 'private' },
  ]
  if (auth.hasPerm('kb_super') || auth.user?.departmentId) {
    opts.splice(1, 0, { label: '部门可见', value: 'department' })
  }
  return opts
})
// 部门必填判断：仅超管（kb_super）选了「部门可见」且未指定部门时必填。
// 非超管有部门时锁定本人部门（无需选择），无部门时看不到 department 选项。
const deptRequired = computed(
  () => uploadScope.value === 'department' && auth.hasPerm('kb_super') && !auth.user?.departmentId,
)
const deptMissing = computed(() => deptRequired.value && !uploadDeptId.value)
// 上传模态框开关（表单 + 进度条一体化）
const uploadOpen = ref(false)

// 上传状态派生：是否有进行中的任务 / 是否全部完成
const hasActiveUpload = computed(() => uploadTasks.value.some((t) => t.status === 'uploading' || t.status === 'processing' || t.status === 'queued'))
const allDone = computed(() => uploadTasks.value.length > 0 && !hasActiveUpload.value)

// 权限范围根据当前视图自动锁定：
// 我的文档(mine)：自由选择（默认 department，无部门权限则 public）
// 公共文档(public)：强制公开可见
// 部门文档(department)：强制部门可见
// 归档(archive)：不显示上传按钮
const uploadScopeLocked = computed(() => {
  if (scope.value === 'public') return 'public'
  if (scope.value === 'department') return 'department'
  return null // mine: 自由选择
})

function openUploadModal() {
  // 根据当前视图预设权限范围
  if (uploadScopeLocked.value) {
    uploadScope.value = uploadScopeLocked.value
  } else {
    // 无锁定时默认「部门可见」，无部门权限则回退「公开可见」
    const hasDeptOpt = uploadScopeOptions.value.some(o => o.value === 'department')
    uploadScope.value = hasDeptOpt ? 'department' : 'public'
  }
  uploadOpen.value = true
}
// 上传弹窗：仅蒙层上明确单击才关闭，拖拽手势不关
const uploadBd = useBackdropClick(closeUploadModal)

function closeUploadModal() {
  if (hasActiveUpload.value) return // 有任务进行中不允许关闭
  uploadOpen.value = false
}

// P5：部门筛选（部门树）
const departments = ref<DepartmentNode[]>([])
const filterDept = ref<string>('')

// 是否有任一筛选器激活（用于显示「重置筛选」按钮）
const hasActiveFilter = computed(() =>
  !!(filterType.value || filterStatus.value || filterScope.value || filterDept.value),
)
function resetFilters() {
  filterType.value = ''
  filterStatus.value = ''
  filterScope.value = ''
  filterDept.value = ''
}

// P5：上传进度（轮询 DocumentTask）
interface UploadTask {
  id: string
  filename: string
  progress: number
  status: 'queued' | 'uploading' | 'processing' | 'done' | 'error'
  message?: string
  file?: File   // 保留原始 File 对象以支持失败重试
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

// 弹窗（AI 审核状态内聚在 DocPreviewModal）
const previewDoc = ref<DocumentDetail | null>(null)
const previewLoading = ref(false)

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
  return q
}

/* ---------- 数据加载（服务端分页 + 真实过滤）---------- */
async function loadDocs(force = false) {
  if (!selectedKb.value) {
    docs.value = []
    total.value = 0
    return
  }
  loading.value = true
  selectedIds.value = []
  try {
    const res = await getDocuments(selectedKb.value, buildQuery() as any, force)
    docs.value = res.items
    total.value = res.total
  } catch (e: unknown) {
    docs.value = []
    total.value = 0
    // 403 无权访问：刷新 KB 列表（后端已按权限过滤）并切换到第一个可用库
    if ((e as any)?.status === 403) {
      await knowledge.reload()
      const next = knowledge.bases.find((b) => b.id !== selectedKb.value)
      if (next) {
        selectedKb.value = next.id
        return // watch(selectedKb) 会触发重新加载
      }
    }
    toast.error(`加载文档失败：${errMsg(e)}`)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!knowledge.loaded) await knowledge.load()
  await loadDepartments()
  if (knowledge.bases.length) {
    selectedKb.value = knowledge.bases[0].id
    await loadDocs()
  }
})

watch(selectedKb, async () => {
  currentPage.value = 1
  selectedIds.value = []
  filterDept.value = ''
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

// P5：部门筛选变化 → 重新拉取（服务端真实过滤）
watch(filterDept, async () => {
  currentPage.value = 1
  await loadDocs()
})

// 上传模态框：关闭时清空进度列表，下次打开是干净状态
watch(uploadOpen, (open) => {
  if (!open) uploadTasks.value = []
})

// 组件存活标志 + 轮询 timer 句柄：卸载后中止一切异步定时任务，
// 避免 pollTask 递归 setTimeout 在后台持续请求（内存泄漏 + 无效流量）。
let alive = true
const pendingTimers = new Set<ReturnType<typeof setTimeout>>()

function trackTimeout(fn: () => void, ms: number) {
  const id = setTimeout(() => {
    pendingTimers.delete(id)
    if (alive) fn()
  }, ms)
  pendingTimers.add(id)
  return id
}

// 组件卸载时移除全局点击监听，避免 popover 打开时切走页面残留监听导致内存泄漏 / 报错；
// 同时中止搜索防抖与上传轮询的全部定时器。
onBeforeUnmount(() => {
  alive = false
  if (searchTimer) clearTimeout(searchTimer)
  for (const id of pendingTimers) clearTimeout(id)
  pendingTimers.clear()
})

/* ---------- P5：部门 / 标签 数据 ---------- */
async function loadDepartments() {
  try {
    departments.value = await getDepartments()
  } catch (e: unknown) {
    departments.value = []
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
  if (s === 'private') return '本人可见'
  if (s === 'department') return '部门可见'
  return '公开可见' // public | 默认
}

function fileMeta(type: string): { icon: string; color: string } {
  const t = (type || '').toUpperCase()
  if (t.includes('PDF')) return { icon: 'pdf', color: '#EF4444' }
  if (t.includes('DOC')) return { icon: 'doc', color: '#3B82F6' }
  if (t.includes('XLS')) return { icon: 'excel', color: '#22C55E' }
  if (t.includes('PPT')) return { icon: 'pptx', color: '#F59E0B' }
  if (t.includes('MD')) return { icon: 'file-code', color: '#8B5CF6' }   // 紫色 — Markdown
  if (t.includes('TXT')) return { icon: 'file-text', color: '#0EA5E9' } // 天蓝 — 纯文本
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
// 选择文件前的拦截：部门可见且当前账号无默认部门时，归属部门必填，
// 未选则阻止打开文件框并提示，避免把请求发到后端才 400。
function onPickClick(e: Event) {
  if (deptMissing.value) {
    e.preventDefault()
    toast.warning('部门可见文档必须指定归属部门（当前账号无默认部门）')
  }
}

async function onUploadFiles(e: Event) {
  // 模态框保持打开以展示上传进度
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length) return
  if (!selectedKb.value) {
    toast.warning('请先在上方选择知识库')
    input.value = ''
    return
  }
  if (deptMissing.value) {
    toast.warning('部门可见文档必须指定归属部门（当前账号无默认部门）')
    input.value = ''
    return
  }
  // 先为所有选中文件在列表里占位（queued，进度 0），用户立刻看到选了哪些；
  // 再由并发池逐个填充真实进度。
  const jobs = files.map((f) => {
    const entry = reactive<UploadTask>({ id: '', filename: f.name, progress: 0, status: 'queued', file: markRaw(f) })
    uploadTasks.value.push(entry)
    return { file: f, entry }
  })
  // 并发上传（同时最多 3 个）：每个文件独立走完 OSS→后端→轮询，
  // 不再逐个串行等待，多文件整体耗时大幅缩短；某个失败只标红该条目，不影响其他。
  await runWithConcurrency(jobs, 3, (job) => uploadOneFile(job.file, job.entry))
  input.value = ''
}

// 重试单个失败文件
function retryOne(entry: UploadTask) {
  if (!entry.file || entry.status !== 'error') return
  entry.status = 'queued'
  entry.progress = 0
  entry.message = undefined
  uploadOneFile(entry.file, entry)
}

// 重试所有失败文件
function retryAllFailed() {
  const failed = uploadTasks.value.filter(t => t.status === 'error' && t.file)
  if (!failed.length) return
  failed.forEach(t => { t.status = 'queued'; t.progress = 0; t.message = undefined })
  runWithConcurrency(failed, 3, (t) => uploadOneFile(t.file!, t))
}

const hasFailed = computed(() => uploadTasks.value.some(t => t.status === 'error' && t.file))

// 单个文件的上传流水线（并发执行，entry 由调用方预创建占位）
async function uploadOneFile(f: File, entry: UploadTask) {
  entry.status = 'uploading' // 从 queued 占位切换为上传中
  try {
    // 优先 OSS 前端直传（后端启用时）；未启用或签名被拒则回退旧 base64 流程
    let doc: DocumentItem
    const deptId = uploadScope.value === 'department' ? (uploadDeptId.value || undefined) : undefined
    try {
      const { url } = await uploadToOss(f, `uploads/docs/${selectedKb.value}`)
      doc = await uploadDocument(selectedKb.value, f.name, { fileUrl: url, scope: uploadScope.value, departmentId: deptId })
    } catch (ossErr: unknown) {
      const msg = errMsg(ossErr, '')
      if (msg.includes('OSS 未启用')) {
        const b64 = await readFileB64(f)
        doc = await uploadDocument(selectedKb.value, f.name, { contentB64: b64, scope: uploadScope.value, departmentId: deptId })
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
    }
  } catch (err: unknown) {
    entry.status = 'error'
    entry.message = errMsg(err)
    toast.error(`上传失败：${f.name} - ${errMsg(err)}`)
  }
}

// 并发池：最多 limit 个任务同时跑，其余排队，避免一次选大量文件打满连接
async function runWithConcurrency<T>(items: T[], limit: number, fn: (item: T) => Promise<void>) {
  let cursor = 0
  const worker = async () => {
    while (cursor < items.length) {
      const idx = cursor++
      await fn(items[idx])
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => worker()))
}

// 轮询单个文档任务的真实进度，平滑补间到目标值（组件卸载后自动停止）
async function pollTask(entry: UploadTask, taskId: string) {
  const tick = async () => {
    if (!alive) return
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
      await loadDocs()
      return
    }
    trackTimeout(() => { void tick() }, 700)
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

/* ---------- 审核 / 删除 ---------- */
async function onApprove(doc: DocumentItem) {
  if (!selectedKb.value) return
  try {
    await approveDocument(selectedKb.value, doc.id)
    toast.success(`已通过审核：${doc.title}`)
    await loadDocs()
  } catch (e: unknown) {
    toast.error(`操作失败：${errMsg(e)}`)
  }
}

async function onReject(doc: DocumentItem) {
  if (!selectedKb.value) return
  try {
    await rejectDocument(selectedKb.value, doc.id)
    toast.success(`已驳回：${doc.title}`)
    await loadDocs()
  } catch (e: unknown) {
    toast.error(`操作失败：${errMsg(e)}`)
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
  } catch (e: unknown) {
    toast.error(`删除失败：${errMsg(e)}`)
  } finally {
    deleting.value = false
  }
}

/* ---------- 预览 ---------- */
async function onPreview(doc: DocumentItem) {
  if (!selectedKb.value) return
  previewLoading.value = true
  previewDoc.value = null
  try {
    previewDoc.value = await getDocument(selectedKb.value, doc.id)
  } catch (e: unknown) {
    toast.error(`预览失败：${errMsg(e)}`)
  } finally {
    previewLoading.value = false
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
  // checked 来自表头 checkbox 的 @change：true=用户勾选全选（应加入），false=取消（应移除）
  if (checked === false) {
    selectedIds.value = selectedIds.value.filter((id) => !pageIds.includes(id))
  } else {
    const set = new Set(selectedIds.value)
    pageIds.forEach((id) => set.add(id))
    selectedIds.value = Array.from(set)
  }
}

function onBatchDelete() {
  if (!selectedIds.value.length || !selectedKb.value) return
  showBatchDelete.value = true
}

const showBatchApprove = ref(false)
const approving = ref(false)
function onBatchApprove() {
  if (!selectedIds.value.length || !selectedKb.value) return
  showBatchApprove.value = true
}
async function confirmBatchApprove() {
  showBatchApprove.value = false
  approving.value = true
  try {
    const res = await batchApproveDocuments(selectedKb.value, selectedIds.value)
    toast.success(`已审核 ${res.approved} 篇，跳过 ${res.skipped} 篇`)
    selectedIds.value = []
    await loadDocs()
  } catch (e: unknown) {
    toast.error(`批量审核失败：${errMsg(e)}`)
  } finally {
    approving.value = false
  }
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
    } catch (e: unknown) {
      toast.error(`删除失败：${errMsg(e)}`)
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
    <!-- ====== 工具栏（双行：主操作行 + 筛选行）====== -->
    <div class="toolbar card">
      <!-- 第一行：主操作行 -->
      <div class="toolbar-main">
        <!-- KB 选择器（严格隔离后仅列当前用户可见的库） -->
        <CustomSelect
          v-model="selectedKb"
          :options="kbOptions"
          placeholder="选择知识库"
          width="200px"
        />
        <!-- 搜索（自适应拉宽） -->
        <div class="search-box">
          <Icon name="search" :size="14" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索文档名称、内容、上传人等" class="search-input" />
          <button v-if="searchQuery" class="search-clear" @click="clearSearch">
            <Icon name="close" :size="12" />
          </button>
        </div>

        <!-- 右侧操作组 -->
        <div class="toolbar-actions">
          <!-- 刷新 -->
          <button class="icon-btn" title="刷新" :disabled="loading" @click="loadDocs(true)">
            <Icon name="refresh" :size="15" :class="{ spin: loading }" />
          </button>

          <!-- 批量上传（归档视图不显示） -->
          <button
            v-if="scope !== 'archive'"
            class="btn btn-primary btn-sm"
            :class="{ 'is-loading': hasActiveUpload }"
            @click="openUploadModal"
          >
            <Icon name="upload" :size="13" /> {{ hasActiveUpload ? '上传中…' : '批量上传' }}
          </button>

          <span class="action-divider"></span>

          <!-- 视图切换 -->
          <button class="btn btn-ghost btn-sm view-toggle" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'">
            <Icon name="listview" :size="16" />
          </button>
          <button class="btn btn-ghost btn-sm view-toggle" :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'">
            <Icon name="gridview" :size="16" />
          </button>
        </div>
      </div>

      <!-- 第二行：筛选行 -->
      <div class="toolbar-filters">
        <span class="filter-label">
          <Icon name="filter" :size="13" /> 筛选
        </span>
        <CustomSelect v-model="filterType" :options="typeOptions" placeholder="文件类型" width="120px" />
        <CustomSelect v-model="filterStatus" :options="statusOptions" placeholder="解析状态" width="120px" />
        <CustomSelect v-model="filterScope" :options="scopeOptions" placeholder="权限范围" width="120px" />

        <!-- P5：部门筛选（弹出部门树，复用 DepartmentTreeSelect） -->
        <DepartmentTreeSelect v-model="filterDept" :nodes="departments" placeholder="部门" top-label="全部部门" />

        <!-- 重置筛选（任一筛选器激活时显示） -->
        <button v-if="hasActiveFilter" class="btn btn-ghost btn-sm" @click="resetFilters">
          <Icon name="close" :size="12" /> 重置筛选
        </button>

        <!-- 选中时显示批量操作（右对齐） -->
        <div v-if="selectedIds.length" class="batch-actions-right">
          <button
            class="btn btn-primary btn-sm"
            :disabled="approving"
            @click="onBatchApprove"
          >
            <Icon name="check" :size="13" /> {{ approving ? '审核中…' : `批量审批（${selectedIds.length}）` }}
          </button>
          <button
            class="btn btn-danger btn-sm"
            :disabled="deleting"
            @click="onBatchDelete"
          >
            <Icon name="trash" :size="13" /> 批量删除（{{ selectedIds.length }}）
          </button>
        </div>
      </div>
    </div>

    <!-- ====== 批量操作条（选中时替换工具栏第一行，不额外占空间）====== -->
    <!-- 旧版独立 batch-bar 已移除，改为内嵌到 toolbar 第一行的选中态 -->

    <!-- ====== 上传模态框（表单 + 进度条一体化）====== -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="uploadOpen" class="modal-overlay" @mousedown="uploadBd.onMouseDown" @mouseup="uploadBd.onMouseUp">
          <div class="upload-modal card">
            <!-- 表单区 -->
            <div class="um-header">
              <span class="um-title">上传文档</span>
              <button v-if="!hasActiveUpload" class="um-close" @click="uploadOpen = false" title="关闭">
                <Icon name="close" :size="16" />
              </button>
            </div>
            <div class="um-body">
              <!-- 权限范围：我的文档可自由选择，公共/部门视图固定显示 -->
              <div class="up-field">
                <span class="up-field-label">权限范围</span>
                <template v-if="uploadScopeLocked">
                  <span class="up-scope-fixed" :class="'scope-' + uploadScopeLocked">
                    {{ uploadScopeLocked === 'public' ? '公开可见' : '部门可见' }}
                  </span>
                </template>
                <CustomSelect v-else v-model="uploadScope" :options="uploadScopeOptions" width="100%" />
              </div>
              <!-- 归属部门：非管理员锁定本人部门；管理员可自由选择 -->
              <div v-if="uploadScope === 'department'" class="up-field">
                <span class="up-field-label">
                  归属部门
                  <span v-if="deptRequired" class="req-mark">*</span>
                </span>
                <template v-if="!auth.hasPerm('kb_super') && auth.user?.departmentId">
                  <span class="up-scope-fixed scope-department">本人部门：{{ auth.user.department }}</span>
                </template>
                <DepartmentSelect
                  v-else
                  v-model="uploadDeptId"
                  :placeholder="deptRequired ? '请选择归属部门（必填）' : '默认本人部门'"
                  :empty-label="deptRequired ? '请选择归属部门（必填）' : '默认本人部门'"
                  width="100%"
                />
                <p v-if="deptMissing" class="up-hint up-hint-error">
                  部门可见文档必须指定归属部门，当前账号无默认部门，请先选择。
                </p>
              </div>
              <label
                class="btn btn-primary btn-sm upload-btn"
                :class="{ 'is-disabled': deptMissing || hasActiveUpload }"
                @click="onPickClick"
              >
                <Icon name="upload" :size="13" /> 选择文件
                <input type="file" multiple accept=".md,.txt,.docx,.pdf,.png,.jpg,.jpeg,.gif,.bmp,.webp,.mp3,.wav,.m4a,.ogg,.flac,.mp4,.mov,.webm,.mkv,.avi" class="file-hidden" @change="onUploadFiles" />
              </label>
              <p class="up-hint">支持 md / txt / docx / pdf / 图片 / 音视频，可多选</p>

              <!-- 进度区：有任务时展示 -->
              <template v-if="uploadTasks.length">
                <div class="um-divider"></div>
                <div class="um-progress-list">
                  <div v-for="t in uploadTasks" :key="(t.id || t.filename)" class="up-item">
                    <Icon
                      :name="t.status === 'error' ? 'alert' : (t.status === 'done' ? 'check' : (t.status === 'queued' ? 'clock' : 'loader'))"
                      :size="14"
                      :class="{ spin: t.status === 'uploading' || t.status === 'processing' }"
                      :style="t.status === 'error' ? 'color:var(--danger)' : (t.status === 'done' ? 'color:var(--success)' : (t.status === 'queued' ? 'color:var(--text-tertiary)' : ''))"
                    />
                    <span class="up-name" :title="t.filename">{{ t.filename }}</span>
                    <div class="up-bar">
                      <div class="up-fill" :class="t.status" :style="{ width: t.progress + '%' }"></div>
                    </div>
                    <span v-if="t.status !== 'error'" class="up-pct">{{ t.progress + '%' }}</span>
                    <button
                      v-else
                      class="up-retry-btn"
                      title="重试"
                      @click="retryOne(t)"
                    >重试</button>
                    <span v-if="t.message && t.status === 'error'" class="up-err-msg">{{ t.message }}</span>
                  </div>
                </div>
              </template>

              <!-- 全部完成提示 -->
              <div v-if="allDone && !hasActiveUpload" class="um-footer">
                <button v-if="hasFailed" class="btn btn-outline btn-sm" @click="retryAllFailed">重试失败项</button>
                <button class="btn btn-primary btn-sm" @click="uploadOpen = false">完成</button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ====== 列表 / 网格 ====== -->
    <div class="card" v-if="viewMode === 'list'">
      <div v-if="scope === 'archive'" class="scope-banner warn">
        <Icon name="archive" :size="14" />
        <span>文档归档：仅展示状态为「已拒绝」的文档。</span>
      </div>
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
              <button class="action-btn preview" title="预览" @click="onPreview(row)"><Icon name="eye" :size="15" /></button>
              <button class="action-btn approve" title="通过审核" @click="onApprove(row)"><Icon name="check" :size="15" /></button>
              <button class="action-btn reject" title="驳回" @click="onReject(row)"><Icon name="close" :size="15" /></button>
              <button class="action-btn danger" title="删除" @click="onDelete(row)"><Icon name="trash" :size="15" /></button>
            </div>
          </template>
        </template>
        <template #empty>
          {{ selectedKb ? '该知识库暂无文档，点击「上传文档」添加' : '请选择左侧知识库' }}
        </template>
      </DataTable>
      <Pagination
        v-if="total > 0"
        v-model:page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        @update:page="loadDocs()"
        @update:page-size="currentPage = 1; loadDocs()"
      />
    </div>

    <!-- 网格视图 -->
    <template v-else>
      <div v-if="scope === 'archive'" class="scope-banner warn card">
        <Icon name="archive" :size="14" />
        <span>文档归档：仅展示状态为「已拒绝」的文档。</span>
      </div>
      <div class="file-grid">
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
            <button class="action-btn preview" title="预览" @click="onPreview(d)"><Icon name="eye" :size="15" /></button>
            <button class="action-btn approve" title="通过审核" @click="onApprove(d)"><Icon name="check" :size="15" /></button>
            <button class="action-btn reject" title="驳回" @click="onReject(d)"><Icon name="close" :size="15" /></button>
            <button class="action-btn danger" title="删除" @click="onDelete(d)"><Icon name="trash" :size="15" /></button>
          </div>
        </div>
        <div v-if="!loading && !docs.length" class="grid-empty">
          {{ selectedKb ? '该知识库暂无文档' : '请选择左侧知识库' }}
        </div>
      </div>
      <Pagination
        v-if="total > 0"
        v-model:page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        @update:page="loadDocs()"
        @update:page-size="currentPage = 1; loadDocs()"
      />
    </template>

    <!-- ====== 预览弹窗（含 AI 辅助审核；拆分组件） ====== -->
    <DocPreviewModal
      :doc="previewDoc"
      :loading="previewLoading"
      :kb-id="selectedKb"
      @close="previewDoc = null"
    />

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
    <ConfirmDialog
      :show="showBatchApprove"
      title="批量审核通过"
      :message="`确认将选中的 ${selectedIds.length} 篇文档批量审核通过？通过后将自动进入检索库。`"
      confirm-text="批量审核"
      @close="showBatchApprove = false"
      @confirm="confirmBatchApprove"
    />
  </div>
</template>

<style scoped>
.docs-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
/* 分区说明横幅（内嵌列表卡内，与卡片内容融合） */
.scope-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  background: transparent;
  color: var(--text-tertiary);
  font-size: 12.5px;
  line-height: 1.5;
}
.scope-banner :deep(svg) { color: var(--text-tertiary); flex-shrink: 0; }
.scope-banner.warn { border-left-color: var(--border); }
.scope-banner.warn :deep(svg) { color: var(--text-tertiary); }

/* ---- 工具栏（双行：主操作行 + 筛选行）---- */
.toolbar {
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: visible;
}
.toolbar-main {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 12px 16px;
}
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.batch-actions-right {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.action-divider {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 2px;
}
/* 第二行：筛选行（底色微区分 + 顶部分隔线） */
.toolbar-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-surface-2);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
}
.filter-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-tertiary);
  font-size: 12.5px;
  margin-right: 2px;
}
/* 搜索框（自适应拉宽） */
.search-box {
  position: relative;
  flex: 1;
  min-width: 220px;
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

/* ---- 上传模态框（居中 overlay）---- */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(4px);
}
.upload-modal {
  width: 440px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.um-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px 12px;
  flex-shrink: 0;
}
.um-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.um-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--dur-fast);
}
.um-close:hover { background: var(--bg-hover); color: var(--text-secondary); }
.um-body {
  padding: 0 18px 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}
.um-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}
.um-progress-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.um-done-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: center;
  font-size: 13px;
  color: var(--success);
  padding: 8px 0 2px;
}
.um-footer {
  padding: 10px 18px 16px;
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
  gap: 8px;
}
.up-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.up-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.up-field-label {
  font-size: 12px;
  color: var(--text-tertiary);
}
.req-mark {
  color: var(--danger, #e5484d);
  font-weight: 700;
  margin-left: 2px;
}
.up-scope-fixed {
  display: inline-flex;
  align-items: center;
  height: 34px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
}
.up-pick {
  justify-content: center;
  width: 100%;
}
.up-pick.is-disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.up-hint {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--text-tertiary);
}
.up-hint-error {
  color: var(--danger, #e5484d);
}

/* 视图切换按钮（基于 .btn-ghost，仅覆盖 active 态） */
.view-toggle.active { background: var(--brand); color: var(--text-on-brand); border-color: var(--brand); }
.icon-btn:disabled { opacity: 0.5; cursor: default; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ---- 上传进度条（模态框内）---- */
.up-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  flex-wrap: wrap;
}
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
.up-retry-btn {
  flex: 0 0 44px;
  font-size: 12px;
  color: var(--brand);
  background: none;
  border: 1px solid var(--brand);
  border-radius: 4px;
  padding: 1px 8px;
  cursor: pointer;
  line-height: 1.4;
  transition: background 0.15s, color 0.15s;
}
.up-retry-btn:hover { background: var(--brand); color: #fff; }
.up-err-msg {
  flex-basis: 100%;
  font-size: 11.5px;
  color: var(--danger);
  margin-left: 34px;
  line-height: 1.4;
}

/* 模态框淡入淡出 */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }


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

.empty-cell {
  text-align: center;
  color: var(--text-tertiary);
  padding: 32px 0 !important;
}

/* ---- 网格视图 ---- */
.file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 14px;
}
.doc-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
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
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}
.grid-empty {
  grid-column: 1 / -1;
  text-align: center;
  color: var(--text-tertiary);
  padding: 40px 0;
}

</style>
