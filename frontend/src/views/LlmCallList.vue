<script setup lang="ts">
// 调用日志「模型调用」tab：浏览 / 检索 / 清空 LLM 调用记录。
// 数据源 llm_call 表，由后端 capture_llm_call 在 LLM 三个调用面
// （stream_chat/chat/tool_call）出口异步写入，记模型/类型/耗时/token/状态/预览。
import { ref, computed, onMounted, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import Pagination from '@/components/ui/Pagination.vue'
import DataTable from '@/components/ui/DataTable.vue'
import type { DataTableColumn } from '@/components/ui/DataTable.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { getLlmCalls, clearLlmCalls } from '@/api'
import type { Paginated, LLMCall } from '@/types/api'

const toast = useToastStore()

/* ---------- 列表（服务端分页 + 过滤） ---------- */
const data = ref<Paginated<LLMCall> | null>(null)
const loading = ref(false)
const searchQuery = ref('')
const typeFilter = ref<string>('all')
const statusFilter = ref<string>('all')
const currentPage = ref(1)
const pageSize = ref(20)

async function load(resetPage = false) {
  if (resetPage) currentPage.value = 1
  loading.value = true
  try {
    data.value = await getLlmCalls(currentPage.value, pageSize.value, {
      requestType: typeFilter.value === 'all' ? null : typeFilter.value,
      status: statusFilter.value === 'all' ? null : statusFilter.value,
      q: searchQuery.value.trim() || null,
    })
  } catch (e: unknown) {
    data.value = null
    toast.error(`加载调用日志失败：${errMsg(e)}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => load())

const rows = computed(() => data.value?.items ?? [])
const total = computed(() => data.value?.total ?? 0)

const columns: DataTableColumn[] = [
  { key: 'createdAt', title: '时间', width: '145px' },
  { key: 'model', title: '模型', width: '104px', strong: true, align: 'center' },
  { key: 'requestType', title: '类型', width: '100px', align: 'center' },
  { key: 'caller', title: '调用方', width: '104px' },
  { key: 'status', title: '状态', width: '78px', align: 'center' },
  { key: 'latencyMs', title: '耗时', width: '80px', align: 'center' },
  { key: 'tokens', title: 'Token 入/出', width: '100px' },
  { key: 'preview', title: '响应预览' },
  { key: 'actions', title: '操作', width: '52px' },
]

const typeOptions = [
  { label: '全部类型', value: 'all' },
  { label: '流式问答', value: 'stream_chat' },
  { label: '非流式', value: 'chat' },
  { label: '工具决策', value: 'tool_call' },
]
const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'error' },
]

function clearSearch() {
  searchQuery.value = ''
  load(true)
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => load(true), 250)
})
watch([typeFilter, statusFilter, pageSize], () => load(true))

/* ---------- 展示辅助 ---------- */
function fmtTime(iso: string, full = false) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  const hm = `${p(d.getHours())}:${p(d.getMinutes())}`
  if (full) return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${hm}:${p(d.getSeconds())}`
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${hm}`
}
function typeLabel(t: string) {
  return t === 'stream_chat' ? '流式问答' : t === 'chat' ? '非流式' : t === 'tool_call' ? '工具决策' : t
}
function statusLabel(s: string) {
  return s === 'success' ? '成功' : s === 'error' ? '失败' : s
}
function fmtLatency(ms: number | null) {
  if (ms == null) return '—'
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms} ms`
}
function fmtTokens(row: LLMCall) {
  if (row.tokensIn == null && row.tokensOut == null) return '—'
  return `${row.tokensIn ?? '—'} / ${row.tokensOut ?? '—'}`
}

/* ---------- 详情弹窗 ---------- */
const detail = ref<LLMCall | null>(null)
function openDetail(row: LLMCall) {
  detail.value = row
}

/* ---------- 清空 ---------- */
const showClear = ref(false)
const clearing = ref(false)
async function confirmClear() {
  clearing.value = true
  try {
    await clearLlmCalls()
    toast.success('已清空调用日志')
    showClear.value = false
    load(true)
  } catch (e: unknown) {
    toast.error(`清空失败：${errMsg(e)}`)
  } finally {
    clearing.value = false
  }
}
</script>

<template>
  <div class="llmcl-body">
    <div class="toolbar">
      <div class="search-box">
        <Icon name="search" :size="14" class="search-icon" />
        <input v-model="searchQuery" type="text" placeholder="搜索模型 / 错误 / 预览" class="search-input" />
        <button v-if="searchQuery" class="search-clear" @click="clearSearch"><Icon name="close" :size="12" /></button>
      </div>
      <CustomSelect v-model="typeFilter" :options="typeOptions" width="130px" />
      <CustomSelect v-model="statusFilter" :options="statusOptions" width="120px" />
      <button class="icon-btn" title="刷新" :disabled="loading" @click="() => load()">
        <Icon name="refresh" :size="15" :class="{ spin: loading }" />
      </button>
      <div style="margin-left:auto">
        <button class="btn btn-ghost btn-sm danger-text" :disabled="total === 0" @click="showClear = true">
          <Icon name="trash" :size="13" /> 清空
        </button>
      </div>
    </div>

    <DataTable :columns="columns" :rows="rows" row-key="id" :loading="loading">
      <template #cell="{ row, col }">
        <template v-if="col.key === 'createdAt'">
          <span class="cell-time">{{ fmtTime(row.createdAt) }}</span>
        </template>
        <template v-else-if="col.key === 'model'">
          <span class="model-cell">{{ row.model }}</span>
        </template>
        <template v-else-if="col.key === 'requestType'">
          <span class="type-badge">{{ typeLabel(row.requestType) }}</span>
        </template>
        <template v-else-if="col.key === 'caller'">
          <span v-if="row.caller" class="caller-cell">{{ row.caller }}</span>
          <span v-else class="dim">—</span>
        </template>
        <template v-else-if="col.key === 'status'">
          <span class="st-badge" :class="row.status === 'error' ? 'st-err' : 'st-ok'">{{ statusLabel(row.status) }}</span>
        </template>
        <template v-else-if="col.key === 'latencyMs'">
          <span class="latency-cell">{{ fmtLatency(row.latencyMs) }}</span>
        </template>
        <template v-else-if="col.key === 'tokens'">
          <span class="tokens-cell">{{ fmtTokens(row) }}</span>
        </template>
        <template v-else-if="col.key === 'preview'">
          <span class="preview-cell">{{ row.preview || '—' }}</span>
        </template>
        <template v-else-if="col.key === 'actions'">
          <div class="row-actions">
            <button class="action-btn" title="查看详情" @click="openDetail(row)"><Icon name="eye" :size="15" /></button>
          </div>
        </template>
      </template>
      <template #empty>暂无调用记录（或当前筛选无匹配）</template>
    </DataTable>

    <Pagination
      v-if="total > 0"
      v-model:page="currentPage"
      v-model:page-size="pageSize"
      :total="total"
      @update:page="load()"
      @update:page-size="load(true)"
    />

    <!-- 详情弹窗 -->
    <AppModal :show="!!detail" title="调用详情" wide @close="detail = null">
      <div v-if="detail" class="detail">
        <div class="d-row"><label>时间</label><span>{{ fmtTime(detail.createdAt, true) }}</span></div>
        <div class="d-row"><label>模型</label><span class="mono">{{ detail.model }}</span></div>
        <div class="d-row"><label>类型</label><span>{{ typeLabel(detail.requestType) }}</span></div>
        <div class="d-row" v-if="detail.caller"><label>调用方</label><span class="mono">{{ detail.caller }}</span></div>
        <div class="d-row"><label>状态</label><span>{{ statusLabel(detail.status) }}</span></div>
        <div class="d-row"><label>耗时</label><span>{{ fmtLatency(detail.latencyMs) }}</span></div>
        <div class="d-row"><label>Token 入/出</label><span>{{ fmtTokens(detail) }}</span></div>
        <div class="d-row" v-if="detail.rid"><label>Request ID</label><span class="mono">{{ detail.rid }}</span></div>
        <div class="d-block" v-if="detail.error">
          <label>错误</label>
          <pre class="d-pre stack">{{ detail.error }}</pre>
        </div>
        <div class="d-block" v-if="detail.preview">
          <label>响应预览（前 200 字）</label>
          <pre class="d-pre">{{ detail.preview }}</pre>
        </div>
      </div>
      <template #foot>
        <button class="btn btn-ghost btn-sm" @click="detail = null">关闭</button>
      </template>
    </AppModal>

    <ConfirmDialog
      :show="showClear"
      title="清空调用日志"
      message="确认清空全部 LLM 调用记录？该操作不可恢复。"
      confirm-text="清空"
      danger
      @close="showClear = false"
      @confirm="confirmClear"
    />
  </div>
</template>

<style scoped>
.llmcl-body { padding: 20px; }
.llmcl-body :deep(.data-table) { table-layout: fixed; }

/* ---- 工具栏 ---- */
.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.search-box { position: relative; width: 220px; }
.search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--text-tertiary); pointer-events: none; }
.search-input {
  width: 100%; height: 34px; padding: 0 30px 0 32px;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  font-size: 13px; background: var(--bg-surface); transition: all var(--dur-fast);
}
.search-input:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); }
.search-clear {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  display: flex; align-items: center; justify-content: center; width: 20px; height: 20px;
  border-radius: 50%; color: var(--text-tertiary); cursor: pointer; background: transparent;
}
.search-clear:hover { background: var(--bg-hover); }
.icon-btn:disabled { opacity: 0.5; cursor: default; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.danger-text { color: var(--danger); }
.danger-text:hover { color: var(--danger); }

/* ---- 单元格 ---- */
.cell-time { font-size: 12px; color: var(--text-secondary); white-space: nowrap; font-variant-numeric: tabular-nums; }
.dim { color: var(--text-tertiary); }
.model-cell { font-family: var(--font-mono, monospace); font-size: 12px; color: var(--text-primary); word-break: break-all; }
.caller-cell { font-family: var(--font-mono, monospace); font-size: 12px; color: var(--accent-violet); }
.latency-cell { font-size: 12px; color: var(--text-secondary); font-variant-numeric: tabular-nums; white-space: nowrap; }
.tokens-cell { font-size: 12px; color: var(--text-secondary); font-variant-numeric: tabular-nums; white-space: nowrap; }
.preview-cell { font-size: 12px; color: var(--text-secondary); display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; }

.type-badge { display: inline-flex; padding: 2px 10px; border-radius: var(--radius-pill); font-size: 12px; font-weight: 500; background: var(--accent-blue-soft); color: var(--accent-blue); white-space: nowrap; }
.st-badge { display: inline-flex; padding: 2px 10px; border-radius: var(--radius-pill); font-size: 12px; font-weight: 500; white-space: nowrap; }
.st-badge.st-ok { background: var(--success-soft, var(--bg-subtle)); color: var(--success, var(--text-secondary)); }
.st-badge.st-err { background: var(--danger-soft); color: var(--danger); }

.row-actions { display: flex; align-items: center; gap: 4px; }

/* ---- 详情弹窗 ---- */
.detail { display: flex; flex-direction: column; gap: 10px; }
.d-row { display: flex; align-items: baseline; gap: 12px; font-size: 13px; }
.d-row label { width: 96px; flex-shrink: 0; color: var(--text-tertiary); }
.d-row span { color: var(--text-primary); word-break: break-all; }
.mono { font-family: var(--font-mono, monospace); font-size: 12px; }
.d-block { display: flex; flex-direction: column; gap: 6px; }
.d-block label { font-size: 13px; color: var(--text-tertiary); }
.d-pre {
  margin: 0; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius-md);
  background: var(--bg-subtle); font-family: var(--font-mono, monospace); font-size: 12px;
  color: var(--text-primary); white-space: pre-wrap; word-break: break-all; max-height: 220px; overflow: auto;
}
.d-pre.stack { max-height: 320px; }
</style>
