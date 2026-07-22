<script setup lang="ts">
// 通用数据表格：统一表格视觉（token 驱动，暗色安全）。
// 列声明式（columns）+ 行数据（rows）；自定义单元格用 #cell 插槽；#empty 自定义空态。
// 可选 selectable（勾选列，勾选事件交给外层处理）；可选 clickable（行点击）。
export interface DataTableColumn {
  key: string
  title: string
  align?: 'left' | 'center' | 'right'
  width?: string
  strong?: boolean // 粗体（原 .col-name）
  mono?: boolean // 等宽灰字（原 .col-time）
  muted?: boolean // 次级灰字（原 .col-content）
}

const props = withDefaults(
  defineProps<{
    columns: DataTableColumn[]
    rows: any[]
    rowKey?: string | ((row: any, index: number) => string | number)
    selectable?: boolean
    selectedKeys?: (string | number)[]
    loading?: boolean
    emptyText?: string
    clickable?: boolean
  }>(),
  {
    rowKey: 'id',
    selectable: false,
    selectedKeys: () => [],
    loading: false,
    emptyText: '暂无数据',
    clickable: false,
  },
)

const emit = defineEmits<{
  'row-click': [row: any]
  'toggle-row': [key: string | number]
  'toggle-all': [checked: boolean]
}>()

function keyOf(row: any, index: number): string | number {
  const k = typeof props.rowKey === 'function' ? props.rowKey(row, index) : row[props.rowKey]
  return k === undefined || k === null ? index : k
}

const selectedSet = (() => new Set(props.selectedKeys)) // ponytail: 简单派生，无需 computed
const allSelected = () =>
  props.rows.length > 0 && props.rows.every((r, i) => selectedSet().has(keyOf(r, i)))

function onRowClick(row: any) {
  if (props.clickable) emit('row-click', row)
}
function onHeaderCheck(e: Event) {
  emit('toggle-all', (e.target as HTMLInputElement).checked)
}
function onRowCheck(e: Event, row: any, i: number) {
  e.stopPropagation()
  emit('toggle-row', keyOf(row, i))
}

function alignClass(a?: string) {
  return a && a !== 'left' ? `align-${a}` : ''
}
const cellColspan = () => props.columns.length + (props.selectable ? 1 : 0)
</script>

<template>
  <div class="data-table-wrap">
    <table class="data-table" :class="{ clickable }">
      <thead>
        <tr>
          <th v-if="selectable" class="col-check">
            <input
              type="checkbox"
              :checked="allSelected()"
              :disabled="!rows.length"
              @change="onHeaderCheck"
            />
          </th>
          <th
            v-for="col in columns"
            :key="col.key"
            :style="col.width ? { width: col.width } : undefined"
            :class="alignClass(col.align)"
          >{{ col.title }}</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, i) in rows"
          :key="keyOf(row, i)"
          :class="{ 'is-selected': selectable && selectedSet().has(keyOf(row, i)) }"
          @click="onRowClick(row)"
        >
          <td v-if="selectable" class="col-check">
            <input
              type="checkbox"
              :checked="selectedSet().has(keyOf(row, i))"
              @change="onRowCheck($event, row, i)"
            />
          </td>
          <td
            v-for="col in columns"
            :key="col.key"
            :class="[alignClass(col.align), { 'is-strong': col.strong, 'is-mono': col.mono, 'is-muted': col.muted }]"
          >
            <slot name="cell" :row="row" :col="col" :index="i">
              {{ row[col.key] }}
            </slot>
          </td>
        </tr>
        <tr v-if="!loading && rows.length === 0">
          <td :colspan="cellColspan()" class="empty-cell">
            <slot name="empty">{{ emptyText }}</slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.data-table-wrap { width: 100%; overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }

.data-table th {
  text-align: left;
  padding: 11px 14px;
  color: var(--text-tertiary);
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.02em;
  white-space: nowrap;
  border-bottom: 1px solid var(--border);
}
.data-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  vertical-align: middle;
}
.data-table tbody tr:last-child td { border-bottom: none; }
.data-table tbody tr:hover { background: var(--bg-hover); }
.data-table tbody tr.is-selected { background: var(--brand-soft); }
.data-table.clickable tbody tr { cursor: pointer; }

.data-table .align-right { text-align: right; }
.data-table .align-center { text-align: center; }

.data-table td.is-strong { font-weight: 600; }
.data-table td.is-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12.5px;
  color: var(--text-tertiary);
  white-space: nowrap;
}
.data-table td.is-muted { color: var(--text-secondary); }

.data-table th.col-check,
.data-table td.col-check {
  width: 44px;
  padding-left: 14px;
  padding-right: 8px;
  text-align: center;
}
.data-table .col-check input {
  width: 15px;
  height: 15px;
  accent-color: var(--brand);
  cursor: pointer;
}

.data-table .empty-cell {
  text-align: center;
  color: var(--text-tertiary);
  padding: 32px 14px;
  font-size: 13px;
}
</style>
