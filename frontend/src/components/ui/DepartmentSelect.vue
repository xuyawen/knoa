<script setup lang="ts">
// 部门选择器：拉取部门树并扁平化为带层级缩进的下拉选项，v-model 绑定 department_id。
// 复用于用户管理（Permission.vue）、个人设置（UserProfileSettingsModal.vue）、
// 文档上传（DocumentLibrary.vue）。空选项值为 ''，表示「未设置部门」。
import { ref, computed, onMounted } from 'vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import { getDepartments } from '@/api'
import type { DepartmentNode } from '@/types/api'

const props = withDefaults(defineProps<{
  modelValue: string
  placeholder?: string
  width?: string
  disabled?: boolean
  /** 是否提供「未设置」空选项（默认 true） */
  allowEmpty?: boolean
  emptyLabel?: string
}>(), {
  placeholder: '请选择部门',
  width: '200px',
  disabled: false,
  allowEmpty: true,
  emptyLabel: '未设置',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const tree = ref<DepartmentNode[]>([])

// 深度优先扁平化：用全角空格做层级缩进，value 为部门 id
const options = computed(() => {
  const flat: { label: string; value: string }[] = []
  const walk = (nodes: DepartmentNode[], depth: number) => {
    for (const n of nodes) {
      flat.push({ label: '\u3000'.repeat(depth) + n.name, value: n.id })
      if (n.children?.length) walk(n.children, depth + 1)
    }
  }
  walk(tree.value, 0)
  if (props.allowEmpty) flat.unshift({ label: props.emptyLabel, value: '' })
  return flat
})

onMounted(async () => {
  try {
    tree.value = await getDepartments()
  } catch {
    tree.value = []
  }
})
</script>

<template>
  <CustomSelect
    :model-value="modelValue"
    :options="options"
    :placeholder="placeholder"
    :width="width"
    :disabled="disabled"
    @update:model-value="(v) => emit('update:modelValue', String(v))"
  />
</template>
