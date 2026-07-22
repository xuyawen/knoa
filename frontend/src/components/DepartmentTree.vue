<script setup lang="ts">
// 部门树（递归）：P5 文档管理「部门筛选」使用。
// 选中节点 emit('select', id)；点「全部部门」emit('select', null) 清空。
import { ref } from 'vue'
import type { DepartmentNode } from '@/types/api'
import Icon from '@/components/ui/Icon.vue'

const props = defineProps<{ nodes: DepartmentNode[]; selectedId?: string | null }>()
const emit = defineEmits<{ (e: 'select', id: string | null): void }>()

// 默认全部展开（当前部门为扁平结构，展开无副作用）
const expanded = ref<Set<string>>(new Set(props.nodes.map((n) => n.id)))

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
  <div class="dept-tree">
    <button class="dept-all" :class="{ active: !selectedId }" @click="onClear">
      <Icon name="users" :size="14" />
      <span>全部部门</span>
    </button>
    <ul class="dept-list">
      <li v-for="node in nodes" :key="node.id" class="dept-item">
        <div class="dept-row" :class="{ active: selectedId === node.id }" @click="onPick(node.id)">
          <button
            v-if="node.children && node.children.length"
            class="dept-toggle"
            @click.stop="toggle(node.id)"
          >
            <Icon :name="expanded.has(node.id) ? 'chevron-down' : 'chevron'" :size="12" />
          </button>
          <span v-else class="dept-toggle-placeholder" />
          <Icon name="folder" :size="14" class="dept-icon" />
          <span class="dept-name">{{ node.name }}</span>
        </div>
        <DepartmentTree
          v-if="node.children && node.children.length && expanded.has(node.id)"
          class="dept-children"
          :nodes="node.children"
          :selected-id="selectedId"
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
  gap: 2px;
  max-height: 320px;
  overflow-y: auto;
  padding: 4px;
}
.dept-all {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
}
.dept-all:hover { background: var(--bg-hover); }
.dept-all.active { background: var(--brand-soft); color: var(--brand); font-weight: 600; }

.dept-list { list-style: none; margin: 0; padding: 0; }
.dept-item { margin: 0; }
.dept-children { padding-left: 16px; border-left: 1px solid var(--border); margin-left: 14px; }

.dept-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 7px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 13px;
}
.dept-row:hover { background: var(--bg-hover); }
.dept-row.active { background: var(--brand-soft); color: var(--brand); font-weight: 600; }

.dept-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  flex-shrink: 0;
}
.dept-toggle-placeholder { width: 18px; flex-shrink: 0; }
.dept-icon { color: var(--text-tertiary); flex-shrink: 0; }
.dept-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
