<script setup lang="ts">
// Toast 容器：挂在 App 根部，读取 toast store 渲染全局提示。
import { useToastStore } from '@/stores/toast'
import Icon from './Icon.vue'

const toast = useToastStore()

const iconFor: Record<string, string> = {
  success: 'check',
  error: 'alert',
  warning: 'alert',
  info: 'bell',
}
</script>

<template>
  <Teleport to="body">
    <div class="toast-wrap">
      <TransitionGroup name="toast">
        <div
          v-for="t in toast.items"
          :key="t.id"
          class="toast"
          :class="`toast-${t.type}`"
          @click="toast.dismiss(t.id)"
        >
          <span class="toast-ic">
            <Icon :name="iconFor[t.type]" :size="15" />
          </span>
          <span class="toast-msg">{{ t.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-wrap {
  position: fixed;
  top: 18px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 2000;
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 240px;
  max-width: 440px;
  padding: 11px 16px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--text-tertiary);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-float);
  font-size: 13px;
  cursor: pointer;
}
.toast-success { border-left-color: var(--success); }
.toast-error { border-left-color: var(--danger); }
.toast-warning { border-left-color: var(--warning); }
.toast-info { border-left-color: var(--info); }

.toast-ic {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.toast-success .toast-ic { color: var(--success); }
.toast-error .toast-ic { color: var(--danger); }
.toast-warning .toast-ic { color: var(--warning); }
.toast-info .toast-ic { color: var(--info); }

.toast-enter-active,
.toast-leave-active {
  transition: all 0.28s var(--ease-out);
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(-12px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}
</style>
