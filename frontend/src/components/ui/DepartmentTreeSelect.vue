<script setup lang="ts">
// 树状部门选择器：触发按钮 + 弹出部门树（DepartmentTree）。
// 复用于文档管理「部门筛选」（topLabel=全部部门）与部门管理「上级部门」表单（topLabel=（无/顶级））。
// 触发按钮视觉与 CustomSelect 的 .c-select-trigger 对齐（同高度/边框/背景/字号、展开 focus ring）；
// 弹层与 CustomSelect 面板同款（bg-surface-2 + radius-md + 同款阴影）。
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import DepartmentTree from '@/components/DepartmentTree.vue'
import Icon from '@/components/ui/Icon.vue'
import type { DepartmentNode } from '@/types/api'

const props = withDefaults(defineProps<{
  /** 选中部门 id；空字符串 '' 表示顶部项（全部部门 / 无/顶级） */
  modelValue: string
  /** 部门树数据（由父级传入，组件本身不拉取，避免重复请求） */
  nodes: DepartmentNode[]
  /** 触发按钮未选中时的占位文案 */
  placeholder?: string
  /** 顶部快捷项文案（筛选「全部部门」／表单「（无/顶级）」） */
  topLabel?: string
  /** 编辑场景需排除的部门 id：该节点及其后代不可选（防止选自身/后代为上级造成循环） */
  excludeId?: string | null
  /** 是否撑满父容器（表单场景 true；筛选栏场景 false 宽度自适应） */
  block?: boolean
}>(), {
  placeholder: '部门',
  topLabel: '全部部门',
  excludeId: null,
  block: false,
})

const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>()

const open = ref(false)
const root = ref<HTMLElement>()
const triggerEl = ref<HTMLElement>()
const popEl = ref<HTMLElement>()

// 排除编辑中的节点及其整棵子树（防止选自身或后代为上级，形成循环引用）
const visibleNodes = computed<DepartmentNode[]>(() => {
  if (!props.excludeId) return props.nodes
  const prune = (nodes: DepartmentNode[]): DepartmentNode[] =>
    nodes
      .filter((n) => n.id !== props.excludeId)
      .map((n) => (n.children?.length ? { ...n, children: prune(n.children) } : n))
  return prune(props.nodes)
})

// 触发按钮显示文案：选中部门名；未选中显示 placeholder
const label = computed(() => {
  if (!props.modelValue) return props.placeholder
  const find = (nodes: DepartmentNode[]): string => {
    for (const n of nodes) {
      if (n.id === props.modelValue) return n.name
      if (n.children?.length) {
        const r = find(n.children)
        if (r) return r
      }
    }
    return ''
  }
  return find(props.nodes) || props.placeholder
})

// 弹层定位样式：弹层 Teleport 到 body（脱离 modal-body 的 overflow:auto 裁剪，
// 否则表单弹窗里的树会被 modal-body 裁掉），position:fixed 用触发器视口坐标定位。
const popStyle = ref({ top: '0px', left: '0px', minWidth: '0px', transform: 'none' })

function positionPopover() {
  const t = triggerEl.value
  if (!t) return
  const rect = t.getBoundingClientRect()
  const margin = 6
  const maxH = 340 // .dept-popover 的 max-height
  const spaceBelow = window.innerHeight - rect.bottom - margin
  const spaceAbove = rect.top - margin
  // 下方空间不足且上方更宽裕 → 向上展开（translateY(-100%) 使弹层底边贴住锚点）
  const openUp = spaceBelow < maxH && spaceAbove > spaceBelow
  popStyle.value = {
    top: openUp ? `${rect.top - margin}px` : `${rect.bottom + margin}px`,
    left: `${rect.left}px`,
    minWidth: `${Math.max(rect.width, 232)}px`,
    transform: openUp ? 'translateY(-100%)' : 'none',
  }
}

function toggle() {
  open.value = !open.value
  if (open.value) positionPopover()
}
function onPick(id: string | null) {
  emit('update:modelValue', id || '')
  open.value = false
}

// 点击组件外部关闭弹层（弹层 Teleport 到 body 不在 root 内，需同时检查两者）
function onDocClickOutside(e: MouseEvent) {
  const target = e.target as Node
  if (root.value?.contains(target)) return
  if (popEl.value?.contains(target)) return
  open.value = false
}
// 外部滚动关闭（fixed 定位不随页面滚动；弹层自身滚动除外）。capture 以捕获 modal-body 等子容器滚动。
function onScrollClose(e: Event) {
  if (popEl.value?.contains(e.target as Node)) return
  open.value = false
}
watch(open, (o) => {
  if (o) {
    document.addEventListener('click', onDocClickOutside)
    window.addEventListener('scroll', onScrollClose, true)
  } else {
    document.removeEventListener('click', onDocClickOutside)
    window.removeEventListener('scroll', onScrollClose, true)
  }
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClickOutside)
  window.removeEventListener('scroll', onScrollClose, true)
})
</script>

<template>
  <div ref="root" class="dept-select" :class="{ block }">
    <button ref="triggerEl" type="button" class="dept-trigger" :class="{ open }" @click.stop="toggle">
      <Icon name="users" :size="13" />
      <span class="dept-trigger-label">{{ label }}</span>
      <Icon name="chevron-down" :size="12" class="dept-trigger-arrow" />
    </button>
    <!-- Teleport 到 body：脱离 modal-body 的 overflow 裁剪（表单弹窗场景弹层曾被裁掉）；fixed + 视口坐标定位 -->
    <Teleport to="body">
      <div v-if="open" ref="popEl" class="dept-popover" :style="popStyle">
        <DepartmentTree
          :nodes="visibleNodes"
          :selected-id="modelValue || null"
          :top-label="topLabel"
          @select="onPick"
        />
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.dept-select { position: relative; display: inline-flex; }
/* 表单场景：撑满父容器（form-row 内 flex:1） */
.dept-select.block { display: flex; flex: 1; min-width: 0; }

/* 触发按钮：与 CustomSelect 的 .c-select-trigger 视觉对齐 */
.dept-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  height: 34px;
  padding: 0 10px 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  text-align: left;
  transition: all var(--dur-fast);
  user-select: none;
  white-space: nowrap;
}
.dept-trigger:hover { border-color: var(--text-tertiary); }
.dept-trigger.open {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.dept-trigger-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dept-trigger-arrow {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform 0.2s ease;
}
.dept-trigger.open .dept-trigger-arrow { transform: rotate(180deg); }

/* 弹层：与 CustomSelect 面板风格一致；Teleport 到 body + position:fixed，
   top/left/min-width 由触发器视口坐标内联计算；z-index 高于模态遮罩（overlay 为 1000） */
.dept-popover {
  position: fixed;
  z-index: 1100;
  max-width: 360px;
  max-height: 340px;
  overflow-y: auto;
  padding: 4px;
  background: var(--bg-surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  animation: dept-pop-in 0.15s var(--ease-out);
}
/* 入场动画仅用 opacity：避免 transform 与向上展开的内联 translateY(-100%) 冲突 */
@keyframes dept-pop-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}
.dept-popover::-webkit-scrollbar { width: 5px; }
.dept-popover::-webkit-scrollbar-track { background: transparent; }
.dept-popover::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
