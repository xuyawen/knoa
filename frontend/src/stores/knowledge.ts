import { defineStore, acceptHMRUpdate } from 'pinia'
import { ref } from 'vue'
import { getKnowledgeBases, getTrending } from '@/api'
import { report } from '@/lib/monitor'
import type { KnowledgeBase, HealthItem, TrendingItem } from '@/types/api'

export const useKnowledgeStore = defineStore('knowledge', () => {
  const bases = ref<KnowledgeBase[]>([])
  const health = ref<HealthItem[]>([])
  const trending = ref<TrendingItem[]>([])
  const activeBase = ref<string | null>(null) // null = 全部知识
  const loaded = ref(false)

  async function load() {
    if (loaded.value) return
    try {
      const [kbResp, trendResp] = await Promise.all([
        getKnowledgeBases(1, 100),
        getTrending(),
      ])
      bases.value = kbResp.knowledgeBases
      health.value = kbResp.health
      trending.value = trendResp
      loaded.value = true
    } catch {
      report({ type: 'knowledge.load_error', level: 'error' })
    }
  }

  // 显式重拉（新建知识库 / 切换后强制刷新，绕过 loaded 缓存）
  async function reload() {
    loaded.value = false
    await load()
  }

  function selectBase(id: string | null) {
    activeBase.value = id
  }

  return { bases, health, trending, activeBase, loaded, load, reload, selectBase }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useKnowledgeStore, import.meta.hot))
}
