<script setup lang="ts">
// 错误管理（系统管理子页）：浏览 / 检索 / 清空错误事件。
// 数据源 error_event 表，由后端 capture_error 异步写入两处：
//   backend = 后端 HTTP 4xx/5xx（observability 中间件）；frontend = 前端上报（/api/events）。
import { ref, computed, onMounted, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import Pagination from '@/components/ui/Pagination.vue'
import DataTable from '@/components/ui/DataTable.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { getErrors, clearErrors } from '@/api'
import type { Paginated, ErrorEvent } from '@/types/api'

const toast = useToastStore()

/* ---------- 列表（服务端分页 + 过滤） ---------- */
const data = ref<Paginated<ErrorEvent> | null>(null)
const loading = ref(false)
const searchQuery = ref('')
const sourceFilter = ref<string>('all')
const levelFilter = ref<string>('all')
const currentPage = ref(1)
const pageSize = ref(20)

async function load(resetPage = false) {
  if (resetPage) currentPage.value = 1
  loading.value = true
  try {
    data.value = await getErrors(currentPage.value, pageSize.value, {
      source: sourceFilter.value === 'all' ? null : sourceFilter.value,
      level: levelFilter.value === 'all' ? null : levelFilter.value,
      q: searchQuery.value.trim() || null,
    })
  } catch (e: unknown) {
    data.value = null
    toast.error(`加载错误列表失败：${errMsg(e)}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => load())

const rows = computed(() => data.value?.items ?? [])
const total = computed(() => data.value?.total ?? 0)

const columns = [
  { key: 'createdAt', title: '时间' },
  { key: 'source', title: '来源' },
  { key: 'level', title: '级别' },
  { key: 'statusCode', title: '状态码' },
  { key: 'method', title: '方法' },
  { key: 'path', title: '路径 / 类型', strong: true },
  { key: 'message', title: '消息' },
  { key: 'actions', title: '操作' },
]

const sourceOptions = [
  { label: '全部来源', value: 'all' },
  { label: '后端', value: 'backend' },
  { label: '前端', value: 'frontend' },
]
const levelOptions = [
  { label: '全部级别', value: 'all' },
  { label: '错误', value: 'error' },
  { label: '警告', value: 'warn' },
  { label: '信息', value: 'info' },
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
watch([sourceFilter, levelFilter, pageSize], () => load(true))

/* ---------- 展示辅助 ---------- */
function fmtTime(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
function sourceLabel(s: string) {
  return s === 'backend' ? '后端' : s === 'frontend' ? '前端' : s
}
function levelLabel(l: string) {
  return l === 'error' ? '错误' : l === 'warn' ? '警告' : l === 'info' ? '信息' : l
}
function levelClass(l: string) {
  return l === 'error' ? 'lv-error' : l === 'warn' ? 'lv-warn' : 'lv-info'
}

/* ---------- 详情弹窗 ---------- */
const detail = ref<ErrorEvent | null>(null)
function openDetail(row: ErrorEvent) {
  detail.value = row
}

/* ---------- 清空 ---------- */
const showClear = ref(false)
const clearing = ref(false)
async function confirmClear() {
  clearing.value = true
  try {
    await clearErrors(sourceFilter.value === 'all' ? null : sourceFilter.value)
    toast.success('已清空错误记录')
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
  <div class="page errmg fade-up">
    <section class="card errmg-body">
      <div class="toolbar">
        <div class="search-box">
          <Icon name="search" :size="14" class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索路径 / 消息" class="search-input" />
          <button v-if="searchQuery" class="search-clear" @click="clearSearch"><Icon name="close" :size="12" /></button>
        </div>
        <CustomSelect v-model="sourceFilter" :options="sourceOptions" width="120px" />
        <CustomSelect v-model="levelFilter" :options="levelOptions" width="120px" />
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
          <template v-else-if="col.key === 'source'">
            <span class="src-badge" :class="row.source">{{ sourceLabel(row.source) }}</span>
          </template>
          <template v-else-if="col.key === 'level'">
            <span class="lv-badge" :class="levelClass(row.level)">{{ levelLabel(row.level) }}</span>
          </template>
          <template v-else-if="col.key === 'statusCode'">
            <span v-if="row.statusCode" class="status-code" :class="row.statusCode >= 500 ? 's5' : 's4'">{{ row.statusCode }}</span>
            <span v-else class="dim">—</span>
          </template>
          <template v-else-if="col.key === 'method'">{{ row.method || '—' }}</template>
          <template v-else-if="col.key === 'path'">
            <span class="path-cell">{{ row.path || row.etype || '—' }}</span>
          </template>
          <template v-else-if="col.key === 'message'">
            <span class="msg-cell">{{ row.message || '—' }}</span>
          </template>
          <template v-else-if="col.key === 'actions'">
            <div class="row-actions">
              <button class="action-btn" title="查看详情" @click="openDetail(row)"><Icon name="eye" :size="15" /></button>
            </div>
          </template>
        </template>
        <template #empty>暂无错误记录（或当前筛选无匹配）</template>
      </DataTable>

      <Pagination
        v-if="total > 0"
        v-model:page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        @update:page="load()"
        @update:page-size="load(true)"
      />
    </section>

    <!-- 详情弹窗 -->
    <AppModal :show="!!detail" title="错误详情" wide @close="detail = null">
      <div v-if="detail" class="detail">
        <div class="d-row"><label>时间</label><span>{{ fmtTime(detail.createdAt) }}</span></div>
        <div class="d-row"><label>来源</label><span>{{ sourceLabel(detail.source) }}</span></div>
        <div class="d-row"><label>级别</label><span>{{ levelLabel(detail.level) }}</span></div>
        <div class="d-row" v-if="detail.statusCode"><label>状态码</label><span>{{ detail.statusCode }}</span></div>
        <div class="d-row" v-if="detail.method"><label>方法</label><span>{{ detail.method }}</span></div>
        <div class="d-row" v-if="detail.path"><label>路径</label><span class="mono">{{ detail.path }}</span></div>
        <div class="d-row" v-if="detail.etype"><label>类型</label><span class="mono">{{ detail.etype }}</span></div>
        <div class="d-row" v-if="detail.url"><label>页面 URL</label><span class="mono">{{ detail.url }}</span></div>
        <div class="d-row" v-if="detail.rid"><label>Request ID</label><span class="mono">{{ detail.rid }}</span></div>
        <div class="d-row" v-if="detail.ip"><label>IP</label><span>{{ detail.ip }}</span></div>
        <div class="d-row" v-if="detail.userAgent"><label>User-Agent</label><span class="ua">{{ detail.userAgent }}</span></div>
        <div class="d-block" v-if="detail.message">
          <label>消息</label>
          <pre class="d-pre">{{ detail.message }}</pre>
        </div>
        <div class="d-block" v-if="detail.stack">
          <label>堆栈</label>
          <pre class="d-pre stack">{{ detail.stack }}</pre>
        </div>
      </div>
      <template #foot>
        <button class="btn btn-ghost btn-sm" @click="detail = null">关闭</button>
      </template>
    </AppModal>

    <ConfirmDialog
      :show="showClear"
      title="清空错误记录"
      :message="sourceFilter === 'all' ? '确认清空全部错误记录？该操作不可恢复。' : `确认清空「${sourceLabel(sourceFilter)}」的错误记录？该操作不可恢复。`"
      confirm-text="清空"
      danger
      @close="showClear = false"
      @confirm="confirmClear"
    />
  </div>
</template>

<style scoped>
.errmg-body { padding: 20px; }

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
.path-cell { font-family: var(--font-mono, monospace); font-size: 12px; color: var(--text-primary); word-break: break-all; }
.msg-cell { font-size: 12px; color: var(--text-secondary); display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; }

.src-badge, .lv-badge { display: inline-flex; padding: 2px 10px; border-radius: var(--radius-pill); font-size: 12px; font-weight: 500; }
.src-badge.backend { background: var(--accent-violet-soft); color: var(--accent-violet); }
.src-badge.frontend { background: var(--accent-blue-soft); color: var(--accent-blue); }
.lv-badge.lv-error { background: var(--danger-soft); color: var(--danger); }
.lv-badge.lv-warn { background: var(--warning-soft, var(--bg-subtle)); color: var(--warning, var(--text-secondary)); }
.lv-badge.lv-info { background: var(--bg-subtle); color: var(--text-secondary); }

.status-code { font-family: var(--font-mono, monospace); font-size: 12px; font-weight: 600; padding: 1px 7px; border-radius: var(--radius-sm); }
.status-code.s5 { background: var(--danger-soft); color: var(--danger); }
.status-code.s4 { background: var(--warning-soft, var(--bg-subtle)); color: var(--warning, var(--text-secondary)); }

.row-actions { display: flex; align-items: center; gap: 4px; }

/* ---- 详情弹窗 ---- */
.detail { display: flex; flex-direction: column; gap: 10px; }
.d-row { display: flex; align-items: baseline; gap: 12px; font-size: 13px; }
.d-row label { width: 84px; flex-shrink: 0; color: var(--text-tertiary); }
.d-row span { color: var(--text-primary); word-break: break-all; }
.d-row .ua { font-size: 12px; color: var(--text-secondary); }
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
