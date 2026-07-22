<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import Icon from './Icon.vue'

export interface SelectOption {
  label: string
  value: string | number
}

const props = withDefaults(defineProps<{
  modelValue: string | number
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  width?: string
}>(), {
  placeholder: '请选择',
  disabled: false,
  width: '200px',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number): void
}>()

const open = ref(false)
const flipUp = ref(false)
const root = ref<HTMLElement>()
const panel = ref<HTMLElement>()

const currentLabel = computed(() => {
  const opt = props.options.find((o) => o.value === props.modelValue)
  return opt?.label || props.placeholder
})

function measure() {
  if (!root.value || !panel.value) return
  const rect = root.value.getBoundingClientRect()
  const ph = panel.value.getBoundingClientRect().height
  const below = window.innerHeight - rect.bottom
  flipUp.value = ph > below && rect.top > below
}

function toggle() {
  if (props.disabled) return
  if (open.value) {
    open.value = false
    return
  }
  open.value = true
  nextTick(measure)
}

function pick(opt: SelectOption) {
  emit('update:modelValue', opt.value)
  open.value = false
}

function onClickOutside(e: MouseEvent) {
  if (root.value && !root.value.contains(e.target as Node)) {
    open.value = false
  }
}

function onResize() {
  if (open.value) measure()
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
  window.removeEventListener('resize', onResize)
})
</script>

<template>
  <div ref="root" class="c-select" :class="{ open, disabled }" :style="{ width }">
    <button type="button" class="c-select-trigger" :disabled="disabled" @click="toggle">
      <span class="c-select-label">{{ currentLabel }}</span>
      <Icon name="chevron-down" :size="12" class="c-select-arrow" />
    </button>
    <Transition :name="flipUp ? 'c-drop-up' : 'c-drop'">
      <div v-if="open" ref="panel" class="c-select-panel" :class="{ up: flipUp }">
        <div
          v-for="opt in options"
          :key="opt.value"
          class="c-select-opt"
          :class="{ active: opt.value === modelValue }"
          @click="pick(opt)"
        >{{ opt.label }}</div>
        <div v-if="!options.length" class="c-select-empty">暂无选项</div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.c-select {
  position: relative;
  display: inline-flex;
  align-items: center;
}
.c-select.disabled { opacity: 0.5; pointer-events: none; }

.c-select-trigger {
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
}
.c-select-trigger:hover { border-color: var(--text-tertiary); }
.c-select.open .c-select-trigger {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.c-select-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.c-select-arrow {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform 0.2s ease;
}
.c-select.open .c-select-arrow { transform: rotate(180deg); }

/* ---- 下拉面板 ---- */
.c-select-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 100;
  width: 100%;
  max-height: 260px;
  overflow-y: auto;
  background: var(--bg-surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  padding: 4px;
}
.c-select-panel.up {
  top: auto;
  bottom: calc(100% + 4px);
}
.c-select-opt {
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-primary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--dur-fast);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.c-select-opt:hover { background: var(--bg-hover); }
.c-select-opt.active {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 500;
}
.c-select-empty {
  padding: 16px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--text-tertiary);
}

/* ---- 过渡动画 ---- */
.c-drop-enter-active { animation: drop-in 0.15s ease-out; }
.c-drop-leave-active { animation: drop-in 0.12s ease-in reverse; }
@keyframes drop-in {
  from { opacity: 0; transform: translateY(-6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.c-drop-up-enter-active { animation: drop-in-up 0.15s ease-out; }
.c-drop-up-leave-active { animation: drop-in-up 0.12s ease-in reverse; }
@keyframes drop-in-up {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 滚动条 */
.c-select-panel::-webkit-scrollbar { width: 5px; }
.c-select-panel::-webkit-scrollbar-track { background: transparent; }
.c-select-panel::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
