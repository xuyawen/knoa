import { ref } from 'vue'

const HISTORY_KEY = 'knoa_search_history'
const MAX_HISTORY = 20

export interface HistoryItem {
  text: string
  time: number // Date.now()
}

// 搜索历史：localStorage 持久化，最近 20 条，去重，带时间戳。
// 兼容旧格式（纯字符串数组），首次加载时自动迁移。
export function useSearchHistory() {
  const history = ref<HistoryItem[]>([])

  function load() {
    try {
      const raw = localStorage.getItem(HISTORY_KEY)
      if (!raw) { history.value = []; return }
      const parsed = JSON.parse(raw)
      // 迁移旧格式：string[] → HistoryItem[]
      if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'string') {
        history.value = (parsed as string[]).map((t) => ({ text: t, time: Date.now() }))
        persist()
      } else {
        history.value = parsed as HistoryItem[]
      }
    } catch {
      history.value = []
    }
  }

  function persist() {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
    } catch { /* ignore */ }
  }

  function save(text: string) {
    if (!text.trim()) return
    const next: HistoryItem[] = [{ text, time: Date.now() }, ...history.value.filter((h) => h.text !== text)].slice(0, MAX_HISTORY)
    history.value = next
    persist()
  }

  function clear() {
    history.value = []
    try { localStorage.removeItem(HISTORY_KEY) } catch { /* ignore */ }
  }

  function remove(text: string) {
    const next = history.value.filter((h) => h.text !== text)
    history.value = next
    persist()
  }

  // ── 统计辅助 ──
  function todayCount(): number {
    const start = new Date(); start.setHours(0, 0, 0, 0)
    return history.value.filter((h) => h.time >= start.getTime()).length
  }

  function weekCount(): number {
    const weekAgo = Date.now() - 7 * 86400000
    return history.value.filter((h) => h.time >= weekAgo).length
  }

  function groupByDate(): { label: string; items: HistoryItem[] }[] {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
    const yesterday = today - 86400000

    const groups: Record<string, HistoryItem[]> = {}
    for (const h of history.value) {
      let key: string
      if (h.time >= today) key = '今天'
      else if (h.time >= yesterday) key = '昨天'
      else {
        const d = new Date(h.time)
        key = `${d.getMonth() + 1}/${d.getDate()}`
      }
      ;(groups[key] ??= []).push(h)
    }

    // 固定顺序：今天 > 昨天 > 更早日期倒序
    const order = Object.keys(groups).sort((a, b) => {
      if (a === '今天') return -1
      if (b === '今天') return 1
      if (a === '昨天') return -1
      if (b === '昨天') return 1
      return b.localeCompare(a)
    })
    return order.map((k) => ({ label: k, items: groups[k]! }))
  }

  return { history, load, save, clear, remove, todayCount, weekCount, groupByDate }
}
