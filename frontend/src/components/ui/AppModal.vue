<script setup lang="ts">
// 通用模态壳：teleport 到 body，背景遮罩 + 居中卡片。
// 复用于所有弹框场景（确认框、会话过期、详情等），配色走 token。
import { watch, onBeforeUnmount } from 'vue'
import Icon from './Icon.vue'

const props = withDefaults(
  defineProps<{
    show: boolean
    title?: string
    wide?: boolean
    closeOnBackdrop?: boolean
  }>(),
  { closeOnBackdrop: true, wide: false },
)

const emit = defineEmits<{ (e: 'close'): void }>()

function onBackdrop() {
  if (props.closeOnBackdrop) emit('close')
}

// 打开时锁滚动；组件在打开状态下被卸载（路由切换/父组件销毁）时也复位，
// 否则 body 会永久 overflow:hidden 导致页面无法滚动。
watch(
  () => props.show,
  (v) => {
    document.body.style.overflow = v ? 'hidden' : ''
  },
)
onBeforeUnmount(() => {
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="overlay" @click.self="onBackdrop">
        <div class="modal" :class="{ wide }" role="dialog" aria-modal="true">
          <header v-if="title || $slots.head" class="modal-head">
            <slot name="head">
              <h3 class="modal-title">{{ title }}</h3>
            </slot>
            <button class="icon-btn modal-x" @click="emit('close')" aria-label="关闭">
              <Icon name="close" :size="18" />
            </button>
          </header>
          <div class="modal-body">
            <slot />
          </div>
          <footer v-if="$slots.foot" class="modal-foot">
            <slot name="foot" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(8, 15, 30, 0.46);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 1000;
}
.modal {
  width: 420px;
  max-width: 100%;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-pop);
  display: flex;
  flex-direction: column;
  max-height: 88vh;
}
.modal.wide {
  width: 680px;
}
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px 12px;
}
.modal-title {
  font-size: 16px;
  font-weight: 700;
  margin: 0;
}
.modal-x {
  width: 30px;
  height: 30px;
  margin: -4px -4px 0 0;
}
.modal-body {
  padding: 4px 20px 18px;
  overflow-y: auto;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.6;
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px 18px;
  border-top: 1px solid var(--border);
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s var(--ease-out);
}
.modal-enter-active .modal,
.modal-leave-active .modal {
  transition: transform 0.22s var(--ease-out), opacity 0.2s;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .modal,
.modal-leave-to .modal {
  transform: translateY(12px) scale(0.98);
  opacity: 0;
}
</style>
