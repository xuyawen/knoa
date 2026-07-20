<script setup lang="ts">
// 确认对话框：复用于删除/批量操作等危险确认。
// 复刻自旧前端 ConfirmDialog 的交互形态，配色改为新 token 体系。
import AppModal from './AppModal.vue'

withDefaults(
  defineProps<{
    show: boolean
    title?: string
    message?: string
    confirmText?: string
    cancelText?: string
    danger?: boolean
  }>(),
  {
    title: '确认操作',
    message: '',
    confirmText: '确定',
    cancelText: '取消',
    danger: false,
  },
)

const emit = defineEmits<{ (e: 'close'): void; (e: 'confirm'): void }>()
</script>

<template>
  <AppModal :show="show" :title="title" @close="emit('close')">
    <p class="confirm-msg">{{ message }}</p>
    <template #foot>
      <button class="btn btn-ghost" @click="emit('close')">{{ cancelText }}</button>
      <button
        class="btn"
        :class="danger ? 'btn-danger' : 'btn-primary'"
        @click="emit('confirm')"
      >
        {{ confirmText }}
      </button>
    </template>
  </AppModal>
</template>

<style scoped>
.confirm-msg {
  margin: 0;
  color: var(--text-secondary);
}
</style>
