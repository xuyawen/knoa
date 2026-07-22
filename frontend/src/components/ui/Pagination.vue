<script setup lang="ts">
// 通用分页条：页码/上下页/每页条数/总数展示。emit update:page / update:pageSize。
import { computed } from 'vue'
import Icon from './Icon.vue'
import CustomSelect from './CustomSelect.vue'

const props = withDefaults(
  defineProps<{
    page: number
    pageSize: number
    total: number
    pageSizes?: number[]
  }>(),
  { pageSizes: () => [10, 20, 50, 100] },
)

const emit = defineEmits<{
  'update:page': [page: number]
  'update:pageSize': [size: number]
}>()

const pages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const visiblePages = computed<(number | string)[]>(() => {
  const max = pages.value
  const cur = props.page
  if (max <= 7) return Array.from({ length: max }, (_, i) => i + 1)
  if (cur <= 4) return [1, 2, 3, 4, 5, '...', max]
  if (cur >= max - 3) return [1, '...', max - 4, max - 3, max - 2, max - 1, max]
  return [1, '...', cur - 1, cur, cur + 1, '...', max]
})

const sizeOptions = computed(() =>
  props.pageSizes.map((s) => ({ value: String(s), label: `${s} 条/页` })),
)

function setPage(p: number) {
  if (p >= 1 && p <= pages.value && p !== props.page) {
    emit('update:page', p)
  }
}

function setSize(v: string | number) {
  const size = Number(v)
  if (size && size !== props.pageSize) {
    emit('update:pageSize', size)
  }
}
</script>

<template>
  <div class="pagination-bar">
    <span class="total-text">共 {{ total }} 条</span>

    <div class="page-nav">
      <button
        class="page-btn nav"
        :disabled="page <= 1"
        @click="setPage(page - 1)"
      >
        <Icon name="chevron-left" :size="14" />
      </button>

      <button
        v-for="(p, idx) in visiblePages"
        :key="`${p}-${idx}`"
        class="page-btn"
        :class="{ active: p === page, ellipsis: p === '...' }"
        :disabled="p === '...'"
        @click="typeof p === 'number' && setPage(p)"
      >
        {{ p }}
      </button>

      <button
        class="page-btn nav"
        :disabled="page >= pages"
        @click="setPage(page + 1)"
      >
        <Icon name="chevron" :size="14" />
      </button>
    </div>

    <div class="size-select">
      <CustomSelect
        :model-value="String(pageSize)"
        :options="sizeOptions"
        width="90px"
        @update:model-value="setSize"
      />
    </div>
  </div>
</template>

<style scoped>
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  padding: 12px 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.total-text {
  flex-shrink: 0;
}

.page-nav {
  display: flex;
  align-items: center;
  gap: 6px;
}

.page-btn {
  min-width: 28px;
  height: 28px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: border-color var(--dur-fast) var(--ease-out),
    background var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}
.page-btn:hover:not(:disabled):not(.active):not(.ellipsis) {
  border-color: var(--brand);
  color: var(--brand);
}
.page-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.page-btn.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.page-btn.ellipsis {
  border-color: transparent;
  background: transparent;
  cursor: default;
}
.page-btn.nav {
  padding: 0;
}

.size-select {
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .pagination-bar {
    flex-wrap: wrap;
    gap: 10px;
    justify-content: center;
  }
  .total-text {
    width: 100%;
    text-align: center;
  }
}
</style>
