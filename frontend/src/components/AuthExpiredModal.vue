<script setup lang="ts">
import Icon from './Icon.vue'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'confirm'): void }>()
</script>

<template>
  <teleport to="body">
    <transition name="aem-fade">
      <!-- 不可关闭：遮罩点击不关闭，无 X 按钮 -->
      <div v-if="open" class="aem-overlay">
        <transition name="aem-pop" appear>
          <div class="aem-card" role="alertdialog" aria-modal="true">
            <div class="aem-icon">
              <Icon name="alert-triangle" :size="26" />
            </div>
            <h3 class="aem-title">登录已失效</h3>
            <p class="aem-msg">身份信息已过期，请重新登录后再继续操作。</p>
            <div class="aem-actions">
              <button class="aem-btn" @click="emit('confirm')">确定</button>
            </div>
          </div>
        </transition>
      </div>
    </transition>
  </teleport>
</template>

<style scoped>
.aem-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000; /* 高于 ConfirmDialog（9999）与 Toast（90） */
  padding: 20px;
}
.aem-card {
  width: 360px;
  max-width: 100%;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-float);
  padding: 28px 24px 22px;
  text-align: center;
}
.aem-icon {
  width: 54px;
  height: 54px;
  margin: 0 auto 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--danger-soft, rgba(239, 68, 68, 0.12));
  color: var(--danger);
}
.aem-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 8px;
  color: var(--text-primary);
}
.aem-msg {
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--text-secondary);
  margin: 0 0 22px;
  word-break: break-word;
}
/* 仅一个「确定」按钮，靠右 */
.aem-actions {
  display: flex;
  justify-content: flex-end;
}
.aem-btn {
  height: 38px;
  padding: 0 22px;
  border-radius: var(--radius-md);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid var(--brand);
  background: var(--brand);
  color: #fff;
  transition: opacity 0.15s ease;
}
.aem-btn:hover {
  opacity: 0.9;
}

/* 遮罩淡入 */
.aem-fade-enter-active,
.aem-fade-leave-active {
  transition: opacity 0.18s ease;
}
.aem-fade-enter-from,
.aem-fade-leave-to {
  opacity: 0;
}
/* 卡片弹出 */
.aem-pop-enter-active {
  transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.22s ease;
}
.aem-pop-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.96);
}
</style>
