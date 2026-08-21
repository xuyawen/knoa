<script setup lang="ts">
// 可搜索用户选择器：边输入边按关键词检索后端用户（getUserList 的 q 参数），
// 用于 KB 成员添加等「用户量大、无法一次性全量下拉」的场景，绕开单页 100 上限。
// 视觉与定位逻辑沿用 CustomSelect（Teleport + fixed + 上翻），保持组件库一致。
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import Icon from './Icon.vue'
import { getUserList } from '@/api/auth'
import { useDebouncedWatch } from '@/composables/useDebouncedWatch'
import type { UserOut } from '@/types/api'

const props = withDefaults(defineProps<{
  excludeIds?: string[]
  placeholder?: string
  width?: string
}>(), {
  excludeIds: () => [],
  placeholder: '搜索用户名 / 姓名',
  width: '220px',
})

const emit = defineEmits<{
  (e: 'select', user: UserOut): void
}>()

const open = ref(false)
const flipUp = ref(false)
const root = ref<HTMLElement>()
const panel = ref<HTMLElement>()
const input = ref<HTMLInputElement>()
const panelStyle = ref({ top: '0px', left: '0px', width: '0px' })

const query = ref('')
const results = ref<UserOut[]>([])
const searching = ref(false)
const searched = ref(false) // 是否已发起过检索（区分「空结果」与「尚未搜索」）

let reqSeq = 0 // 请求序号：丢弃乱序返回的旧结果，避免快键输入时旧响应覆盖新结果

function measure() {
  if (!root.value || !panel.value) return
  const rect = root.value.getBoundingClientRect()
  const ph = panel.value.offsetHeight
  const below = window.innerHeight - rect.bottom - 4
  const shouldFlip = ph > below && rect.top > below
  flipUp.value = shouldFlip
  if (shouldFlip) {
    panelStyle.value = { top: `${rect.top - ph - 4}px`, left: `${rect.left}px`, width: `${rect.width}px` }
  } else {
    panelStyle.value = { top: `${rect.bottom + 4}px`, left: `${rect.left}px`, width: `${rect.width}px` }
  }
}

async function runSearch(kw: string) {
  const seq = ++reqSeq
  searching.value = true
  try {
    const page = await getUserList(1, 20, null, kw || null)
    if (seq !== reqSeq) return // 已有更新的请求，丢弃本次
    const excluded = new Set(props.excludeIds)
    results.value = page.items.filter((u) => !excluded.has(u.id))
    searched.value = true
  } catch {
    if (seq === reqSeq) results.value = []
  } finally {
    if (seq === reqSeq) {
      searching.value = false
      nextTick(measure)
    }
  }
}

// 输入即搜索（统一 300ms 防抖，见 useDebouncedWatch）
const { cancel: cancelSearchDebounce } = useDebouncedWatch(query, () => void runSearch(query.value.trim()))

function openPanel() {
  if (open.value) return
  open.value = true
  // 首次打开（尚未搜索）先拉一页用户，避免下拉空白
  if (!searched.value) void runSearch(query.value.trim())
  nextTick(() => {
    measure()
    input.value?.focus()
  })
}

function pick(u: UserOut) {
  emit('select', u)
  query.value = ''
  cancelSearchDebounce() // 清空输入会触发防抖 watcher，撤销它避免多发一次全量检索
  results.value = []
  searched.value = false
  open.value = false
}

function onClickOutside(e: MouseEvent) {
  if (root.value && !root.value.contains(e.target as Node)) open.value = false
}
function onReposition() {
  if (open.value) measure()
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  window.addEventListener('resize', onReposition)
  window.addEventListener('scroll', onReposition, true)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
  window.removeEventListener('resize', onReposition)
  window.removeEventListener('scroll', onReposition, true)
})
</script>

<template>
  <div ref="root" class="u-search" :class="{ open }" :style="{ width }">
    <div class="u-search-trigger" @click="openPanel">
      <Icon name="search" :size="14" class="u-search-icon" />
      <input
        ref="input"
        v-model="query"
        class="u-search-input"
        :placeholder="placeholder"
        @focus="openPanel"
      />
    </div>
    <Teleport to="body">
      <Transition :name="flipUp ? 'u-drop-up' : 'u-drop'">
        <div v-if="open" ref="panel" class="u-search-panel" :style="panelStyle">
          <div v-if="searching" class="u-search-state">
            <Icon name="loader" :size="13" class="u-search-spin" /> 搜索中…
          </div>
          <template v-else>
            <div
              v-for="u in results"
              :key="u.id"
              class="u-search-opt"
              @click="pick(u)"
            >
              <div class="u-search-main">
                <span class="u-search-name">{{ u.displayName || u.username }}</span>
                <span class="u-search-uname">@{{ u.username }}</span>
              </div>
              <div v-if="u.department || u.employeeId" class="u-search-meta">
                <span v-if="u.department">{{ u.department }}</span>
                <span v-if="u.department && u.employeeId" class="u-search-dot">·</span>
                <span v-if="u.employeeId">工号 {{ u.employeeId }}</span>
              </div>
            </div>
            <div v-if="!results.length" class="u-search-state">
              {{ searched ? '无匹配用户' : '输入关键词搜索' }}
            </div>
          </template>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.u-search {
  position: relative;
  display: inline-flex;
  align-items: center;
}
.u-search-trigger {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  height: 34px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  cursor: text;
  transition: all var(--dur-fast);
}
.u-search-trigger:hover { border-color: var(--text-tertiary); }
.u-search.open .u-search-trigger {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.u-search-icon { flex-shrink: 0; color: var(--text-tertiary); }
.u-search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
}
.u-search-input::placeholder { color: var(--text-tertiary); }

/* ---- 下拉面板 ---- */
.u-search-panel {
  position: fixed;
  z-index: 9999;
  max-height: 280px;
  overflow-y: auto;
  background: var(--bg-surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  padding: 4px;
}
.u-search-opt {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 2px;
  padding: 7px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--dur-fast);
}
.u-search-opt:hover { background: var(--bg-hover); }
.u-search-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.u-search-name {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.u-search-uname {
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
}
.u-search-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.u-search-dot { opacity: 0.6; }
.u-search-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 16px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--text-tertiary);
}
.u-search-spin { animation: u-search-rot 0.7s linear infinite; }
@keyframes u-search-rot { to { transform: rotate(360deg); } }

/* ---- 过渡动画 ---- */
.u-drop-enter-active { animation: u-drop-in 0.15s ease-out; }
.u-drop-leave-active { animation: u-drop-in 0.12s ease-in reverse; }
@keyframes u-drop-in {
  from { opacity: 0; transform: translateY(-6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.u-drop-up-enter-active { animation: u-drop-in-up 0.15s ease-out; }
.u-drop-up-leave-active { animation: u-drop-in-up 0.12s ease-in reverse; }
@keyframes u-drop-in-up {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 滚动条 */
.u-search-panel::-webkit-scrollbar { width: 5px; }
.u-search-panel::-webkit-scrollbar-track { background: transparent; }
.u-search-panel::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
