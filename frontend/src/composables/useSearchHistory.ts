import { ref } from 'vue'

const HISTORY_KEY = 'knoa_search_history'
const MAX_HISTORY = 20

// 搜索历史：localStorage 持久化，最近 20 条，去重。
export function useSearchHistory() {
  const history = ref<string[]>([])

  function load() {
    try {
      const raw = localStorage.getItem(HISTORY_KEY)
      history.value = raw ? (JSON.parse(raw) as string[]) : []
    } catch {
      history.value = []
    }
  }

  function save(text: string) {
    if (!text.trim()) return
    const next = [text, ...history.value.filter((h) => h !== text)].slice(0, MAX_HISTORY)
    history.value = next
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
    } catch {
      /* ignore */
    }
  }

  function clear() {
    history.value = []
    try {
      localStorage.removeItem(HISTORY_KEY)
    } catch {
      /* ignore */
    }
  }

  function remove(text: string) {
    const next = history.value.filter((h) => h !== text)
    history.value = next
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
    } catch {
      /* ignore */
    }
  }

  return { history, load, save, clear, remove }
}
