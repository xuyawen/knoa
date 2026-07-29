<script setup lang="ts">
// 部门树（递归）：P5 文档管理「部门筛选」使用。
// 选中节点 emit('select', id)；点「全部部门」emit('select', null) 清空。
// depth 区分层级：0 为顶层（渲染「全部部门」快捷项 + 分割线），>0 为子级（纯树节点），
// 避免递归时每一层都重复渲染「全部部门」。
import { ref, watch } from 'vue'
import type { DepartmentNode } from '@/types/api'
import Icon from '@/components/ui/Icon.vue'

const props = withDefaults(defineProps<{
  nodes: DepartmentNode[]
  selectedId?: string | null
  /** 递归层级：0 顶层，>0 子级 */
  depth?: number
  /** 顶部快捷项文案（筛选场景「全部部门」／表单场景「（无/顶级）」） */
  topLabel?: string
}>(), {
  selectedId: null,
  depth: 0,
  topLabel: '全部部门',
})
const emit = defineEmits<{ (e: 'select', id: string | null): void }>()

// 默认全部展开。顶层 nodes 可能异步加载后才传入，若仅在 setup 初始化一次，
// 数据到达时 expanded 仍为空 → 整棵树折叠；故用 watch 随数据补充新节点 id。
const expanded = ref<Set<string>>(new Set())
watch(
  () => props.nodes,
  (nodes) => {
    const s = new Set(expanded.value)
    for (const n of nodes) if (n.children?.length) s.add(n.id)
    expanded.value = s
  },
  { immediate: true, deep: true },
)

function toggle(id: string) {
  const s = new Set(expanded.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  expanded.value = s
}
function onPick(id: string | null) {
  emit('select', id)
}
function onClear() {
  emit('select', null)
}
</script>

<template>
  <div class="dept-tree" :class="{ 'dept-tree--child': depth > 0 }">
    <!-- 顶层：「全部部门」快捷项 + 分割线（子级不渲染） -->
    <template v-if="depth === 0">
      <button class="dept-all" :class="{ active: !selectedId }" @click="onClear">
        <Icon name="users" :size="15" />
        <span>{{ topLabel }}</span>
      </button>
      <div class="dept-divider" />
    </template>

    <ul class="dept-list">
      <li v-for="node in nodes" :key="node.id" class="dept-item">
        <div class="dept-row" :class="{ active: selectedId === node.id }" @click="onPick(node.id)">
          <button
            v-if="node.children && node.children.length"
            class="dept-toggle"
            :class="{ expanded: expanded.has(node.id) }"
            :aria-expanded="expanded.has(node.id)"
            @click.stop="toggle(node.id)"
          >
            <Icon name="chevron" :size="12" />
          </button>
          <span v-else class="dept-toggle-spacer" />
          <Icon name="folder" :size="15" class="dept-icon" />
          <span class="dept-name">{{ node.name }}</span>
        </div>
        <DepartmentTree
          v-if="node.children && node.children.length && expanded.has(node.id)"
          class="dept-children"
          :nodes="node.children"
          :selected-id="selectedId"
          :depth="depth + 1"
          @select="onPick"
        />
      </li>
    </ul>
  </div>
</template>

<style scoped>
.dept-tree {
  display: flex;
  flex-direction: column;
  padding: 4px;
}
/* 子级树不带外层 padding，缩进统一由 .dept-children 控制 */
.dept-tree--child { padding: 0; }

/* 「全部部门」快捷项（顶层，与下方树节点视觉分区） */
.dept-all {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  text-align: left;
  transition: background var(--dur-fast), color var(--dur-fast);
}
.dept-all:hover { background: var(--bg-hover); color: var(--text-primary); }
.dept-all.active { background: var(--brand-soft); color: var(--brand); font-weight: 600; }

/* 分割线：区隔「全部部门」与部门树 */
.dept-divider {
  height: 1px;
  background: var(--border);
  margin: 5px 6px;
  flex-shrink: 0;
}

.dept-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 1px; }
.dept-item { margin: 0; }

/* 子级树：缩进 + 左侧引导线，层级一目了然 */
.dept-children {
  margin-left: 17px;
  padding-left: 10px;
  border-left: 1px solid var(--border);
}

.dept-row {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 13px;
  transition: background var(--dur-fast), color var(--dur-fast);
}
.dept-row:hover { background: var(--bg-hover); color: var(--text-primary); }
.dept-row.active { background: var(--brand-soft); color: var(--brand); font-weight: 600; }

/* 展开/折叠箭头：右箭头旋转 90° 表示展开，带过渡动画 */
.dept-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  padding: 0;
  border: none;
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  flex-shrink: 0;
  transition: color var(--dur-fast);
}
.dept-toggle:hover { color: var(--text-primary); }
.dept-toggle svg { transition: transform 0.18s var(--ease-out); }
.dept-toggle.expanded svg { transform: rotate(90deg); }

/* 叶子节点占位：保持同级图标纵向对齐 */
.dept-toggle-spacer { width: 16px; flex-shrink: 0; }

.dept-icon { color: var(--text-tertiary); flex-shrink: 0; transition: color var(--dur-fast); }
.dept-row:hover .dept-icon,
.dept-row.active .dept-icon { color: inherit; }

/* min-width:0 使 ellipsis 在 flex 容器中生效 */
.dept-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
