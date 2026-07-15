<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import Icon from './Icon.vue'
import { useUiStore } from '@/stores/ui'
import { useChatStore } from '@/stores/chat'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'

const ui = useUiStore()
const chat = useChatStore()
const knowledge = useKnowledgeStore()
const auth = useAuthStore()
const router = useRouter()
const { toggle: toggleTheme } = useTheme()

const query = ref('')
const inputEl = ref<HTMLInputElement | null>(null)
const selected = ref(0)

interface Cmd {
  id: string
  group: string
  title: string
  icon: string
  run: () => void
}

function go(path: string) {
  if (router.currentRoute.value.path !== path) router.push(path)
  ui.closePalette()
}

function ask(q: string) {
  const fire = () => chat.ask(q, knowledge.activeBase)
  if (router.currentRoute.value.path !== '/') router.push('/').then(fire)
  else fire()
  ui.closePalette()
}

const commands = computed<Cmd[]>(() => {
  const q = query.value.trim().toLowerCase()
  const list: Cmd[] = [
    { id: 'nav-workbench', group: '导航', title: '前往 工作台', icon: 'home', run: () => go('/') },
    { id: 'nav-kb', group: '导航', title: '前往 知识库', icon: 'library', run: () => go('/knowledge-bases') },
    { id: 'nav-history', group: '导航', title: '前往 问答记录', icon: 'clock', run: () => go('/history') },
  ]
  if (auth.isAdmin) {
    list.push({ id: 'nav-users', group: '导航', title: '前往 用户管理', icon: 'users', run: () => go('/users') })
  }
  list.push(
    { id: 'act-theme', group: '操作', title: '切换主题（亮 / 暗）', icon: 'sun', run: () => { toggleTheme(); ui.closePalette() } },
    { id: 'act-logout', group: '操作', title: '退出登录', icon: 'logout', run: () => { auth.logout(); router.replace('/login') } },
  )
  const filtered = q ? list.filter((c) => c.title.toLowerCase().includes(q)) : list
  const text = query.value.trim()
  if (text) {
    filtered.push({
      id: 'ask',
      group: '提问',
      title: `向知海提问：${text}`,
      icon: 'sparkle',
      run: () => ask(text),
    })
  }
  return filtered
})

// 列表变化（过滤后）重置选中项
watch(commands, () => { selected.value = 0 })

// 打开时清空查询、聚焦输入框、重置选中
watch(() => ui.paletteOpen, (open) => {
  if (open) {
    query.value = ''
    selected.value = 0
    nextTick(() => inputEl.value?.focus())
  }
})

function onKeydown(e: KeyboardEvent) {
  // ⌘K / Ctrl+K 全局切换
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    ui.togglePalette()
    return
  }
  if (!ui.paletteOpen) return
  if (e.key === 'Escape') {
    e.preventDefault()
    ui.closePalette()
  } else if (e.key === 'ArrowDown') {
    e.preventDefault()
    selected.value = Math.min(selected.value + 1, commands.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    selected.value = Math.max(selected.value - 1, 0)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const c = commands.value[selected.value]
    if (c) c.run()
  }
}

function onSelect(i: number) {
  selected.value = i
}

function runCommand(cmd: Cmd) {
  cmd.run()
}

// 全局键盘监听（palette 常驻，自身管理快捷键与显隐）
window.addEventListener('keydown', onKeydown)
</script>

<template>
  <transition name="palette-fade">
    <div v-if="ui.paletteOpen" class="overlay" @click.self="ui.closePalette()">
      <div class="palette" role="dialog" aria-label="命令面板">
        <div class="search-row">
          <Icon name="search" :size="16" />
          <input
            ref="inputEl"
            v-model="query"
            placeholder="搜索命令，或直接向知海提问…"
            spellcheck="false"
            autocomplete="off"
          />
          <kbd class="esc">ESC</kbd>
        </div>

        <div class="list">
          <template v-for="(cmd, i) in commands" :key="cmd.id">
            <div v-if="i === 0 || commands[i - 1].group !== cmd.group" class="group">
              {{ cmd.group }}
            </div>
            <button
              class="item"
              :class="{ active: i === selected }"
              @mousemove="onSelect(i)"
              @click="runCommand(cmd)"
            >
              <Icon :name="cmd.icon" :size="16" />
              <span class="label">{{ cmd.title }}</span>
              <span v-if="i === selected" class="hint">↵</span>
            </button>
          </template>
          <div v-if="commands.length === 0" class="empty">无匹配命令</div>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 12vh;
  z-index: 100;
}
.palette {
  width: 560px;
  max-width: calc(100vw - 32px);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-float);
  overflow: hidden;
}
.search-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.search-row input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 15px;
}
.search-row input::placeholder {
  color: var(--text-placeholder);
}
.esc {
  font-size: 11px;
  padding: 2px 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-secondary);
}
.list {
  max-height: 52vh;
  overflow-y: auto;
  padding: 6px;
}
.group {
  font-size: 11px;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  padding: 10px 10px 4px;
}
.item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-primary);
  font-size: 14px;
  text-align: left;
  cursor: pointer;
}
.item.active {
  background: var(--brand-soft);
  color: var(--brand);
}
.item .label {
  flex: 1;
}
.item .hint {
  color: var(--text-secondary);
  font-size: 12px;
}
.empty {
  padding: 24px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
}
.palette-fade-enter-active,
.palette-fade-leave-active {
  transition: opacity 0.15s ease;
}
.palette-fade-enter-from,
.palette-fade-leave-to {
  opacity: 0;
}
</style>
