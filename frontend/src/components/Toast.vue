<script setup lang="ts">
import Icon from './Icon.vue'
import { useToast } from '@/composables/useToast'

const { state, dismiss } = useToast()
</script>

<template>
  <Teleport to="body">
    <transition name="toast-fade">
      <div
        v-if="state.visible"
        class="toast"
        :class="state.type"
        role="status"
        @click="dismiss"
      >
        <Icon :name="state.type === 'success' ? 'check' : 'alert-circle'" :size="16" class="toast-icon" />
        <span>{{ state.message }}</span>
      </div>
    </transition>
  </Teleport>
</template>

<style scoped>
.toast {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 90;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 90vw;
  padding: 11px 18px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18);
}
.toast.success {
  background: #16a34a;
  border: 1px solid #15803d;
  color: #ffffff;
}
.toast.error {
  background: #dc2626;
  border: 1px solid #b91c1c;
  color: #ffffff;
}
.toast-icon { flex: none; opacity: 0.95; }
.toast-fade-enter-active,
.toast-fade-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.toast-fade-enter-from,
.toast-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(-8px); }
</style>
