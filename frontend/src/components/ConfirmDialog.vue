<script setup lang="ts">
import Icon from './Icon.vue'
import { useConfirmState, useConfirm } from '@/composables/useConfirm'

const state = useConfirmState()
const { onConfirmClick, onCancelClick } = useConfirm()
</script>

<template>
  <teleport to="body">
    <transition name="cd-fade">
      <div v-if="state.visible" class="cd-overlay" @click.self="onCancelClick">
        <transition name="cd-pop" appear>
          <div class="cd-card" :class="{ danger: state.danger }" role="alertdialog" aria-modal="true">
            <div class="cd-icon" :class="{ danger: state.danger }">
              <Icon :name="state.icon" :size="22" />
            </div>
            <h3 class="cd-title">{{ state.title }}</h3>
            <p class="cd-msg">{{ state.message }}</p>
            <div class="cd-actions">
              <button class="cd-btn cancel" @click="onCancelClick" :disabled="state.loading">
                {{ state.cancelText }}
              </button>
              <button
                class="cd-btn confirm"
                :class="{ danger: state.danger }"
                @click="onConfirmClick"
                :disabled="state.loading"
              >
                <span v-if="state.loading" class="cd-spin" />
                {{ state.loading ? '处理中…' : state.confirmText }}
              </button>
            </div>
          </div>
        </transition>
      </div>
    </transition>
  </teleport>
</template>

<style scoped>
.cd-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}
.cd-card {
  width: 360px;
  max-width: 100%;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-float);
  padding: 28px 24px 22px;
  text-align: center;
}
.cd-icon {
  width: 52px;
  height: 52px;
  margin: 0 auto 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--brand-soft);
  color: var(--brand);
}
.cd-icon.danger {
  background: var(--danger-soft, rgba(239, 68, 68, 0.12));
  color: var(--danger);
}
.cd-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 8px;
  color: var(--text-primary);
}
.cd-msg {
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--text-secondary);
  margin: 0 0 22px;
  word-break: break-word;
}
.cd-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}
.cd-btn {
  height: 38px;
  flex: 1;
  border-radius: var(--radius-md);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: background 0.15s ease, border-color 0.15s ease, opacity 0.15s ease;
}
.cd-btn.cancel:hover {
  background: var(--bg-subtle);
}
.cd-btn.confirm {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.cd-btn.confirm:hover:not(:disabled) {
  opacity: 0.9;
}
.cd-btn.confirm.danger {
  background: var(--danger);
  border-color: var(--danger);
}
.cd-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.cd-spin {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: cd-rotate 0.7s linear infinite;
}
@keyframes cd-rotate {
  to { transform: rotate(360deg); }
}

/* 遮罩淡入 */
.cd-fade-enter-active,
.cd-fade-leave-active {
  transition: opacity 0.18s ease;
}
.cd-fade-enter-from,
.cd-fade-leave-to {
  opacity: 0;
}
/* 卡片弹出 */
.cd-pop-enter-active {
  transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.22s ease;
}
.cd-pop-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.96);
}
</style>
