<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import Icon from './Icon.vue'
import { useChatStore } from '@/stores/chat'
import { useKnowledgeStore } from '@/stores/knowledge'

const text = ref('')
const emit = defineEmits<{ (e: 'send', q: string): void }>()

const chat = useChatStore()
const knowledge = useKnowledgeStore()

// 知识域 chip → 内联 KB 选择器，直接驱动 chat.filterKb（与聊天头部下拉同源）
const kbMenuOpen = ref(false)
const kbWrap = ref<HTMLElement | null>(null)

const kbOptions = computed(() => [
  { label: '全部知识库', key: null as string | null },
  ...knowledge.bases.map((b) => ({ label: b.name, key: b.id })),
])

const kbLabel = computed(() => {
  const f = kbOptions.value.find((o) => o.key === chat.filterKb)
  return f?.label || '全部知识库'
})

function toggleKbMenu() {
  kbMenuOpen.value = !kbMenuOpen.value
}

function selectKb(key: string | null) {
  chat.filterKb = key
  kbMenuOpen.value = false
}

function onClickOutside(e: MouseEvent) {
  if (kbWrap.value && !kbWrap.value.contains(e.target as Node)) {
    kbMenuOpen.value = false
  }
}

function send() {
  const q = text.value.trim()
  if (!q) return
  emit('send', q)
  text.value = ''
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

onMounted(() => document.addEventListener('click', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside))
</script>

<template>
  <div class="composer">
    <div class="box">
      <textarea
        v-model="text"
        placeholder="向知海提问…（Enter 发送，Shift+Enter 换行）"
        @keydown="onKey"
        rows="1"
      />
      <div class="row">
        <div class="left" ref="kbWrap">
          <!-- 附件 chip：聊天无附件上传管线（后端 /api/ask 不支持），暂移除，避免假按钮 -->
          <!-- 知识域 chip：内联 KB 选择器，驱动检索范围 -->
          <button class="chip" :class="{ active: chat.filterKb }" @click.stop="toggleKbMenu">
            <Icon name="selection" :size="15" />
            知识域：{{ kbLabel }}
          </button>
          <transition name="kbmenu">
            <div v-if="kbMenuOpen" class="kb-menu">
              <button
                v-for="o in kbOptions"
                :key="o.key ?? '__all__'"
                class="kb-item"
                :class="{ active: o.key === chat.filterKb }"
                @click="selectKb(o.key)"
              >
                {{ o.label }}
              </button>
            </div>
          </transition>
        </div>
        <button class="send" @click="send" title="发送">
          <Icon name="send" :size="18" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.composer {
  flex-shrink: 0;
  padding: 16px 24px 20px;
  background: var(--bg-page);
}
.box {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 12px 14px 10px;
  box-shadow: var(--shadow-card);
  transition: border-color 0.15s ease;
}
.box:focus-within {
  border-color: var(--brand);
}
textarea {
  width: 100%;
  display: block;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
  max-height: 120px;
}
textarea::placeholder {
  color: var(--text-placeholder);
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}
.left {
  position: relative;
  display: flex;
  gap: 8px;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 12px;
  border-radius: var(--radius-pill);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-size: 13px;
  transition: color 0.15s ease, background 0.15s ease;
}
.chip:hover,
.chip.active {
  color: var(--brand);
  background: var(--brand-soft);
}
.kb-menu {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  min-width: 180px;
  max-height: 260px;
  overflow-y: auto;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-float);
  z-index: 50;
  padding: 4px;
}
.kb-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.12s ease;
  white-space: nowrap;
}
.kb-item:hover {
  background: var(--bg-subtle);
}
.kb-item.active {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
}
.kbmenu-enter-active,
.kbmenu-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.kbmenu-enter-from,
.kbmenu-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
.send {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease, transform 0.12s ease;
}
.send:hover {
  background: var(--brand-hover);
}
.send:active {
  transform: scale(0.94);
}
</style>
